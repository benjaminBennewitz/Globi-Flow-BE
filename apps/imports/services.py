# apps/imports/services.py

"""Orchestriert die lokale Importpipeline für Laborbefunde."""

from statistics import mean

from django.db import transaction

from apps.imports.models import ImportDataset, ImportJob, ImportStep
from apps.imports.parser import parse_lab_values
from apps.imports.pdf_analysis import analyze_pdf
from apps.imports.service_persistence import (
    create_datasets,
    deduplicate_parsed_values,
    review_hints_for_value,
    save_lab_value,
    should_review_value,
    sync_review_candidate,
)
from apps.imports.service_setup import (
    create_default_steps,
    create_upload_job,
    ensure_analyte,
    ensure_reference,
    ensure_unit,
    extract_report_date,
    log,
    mark_job_error,
    mark_ocr_started,
    set_step,
    status_for_value,
    unique_public_id,
)
from apps.labs.models import LabReport, LabValue, ReviewCandidate
from apps.patients.models import Patient

__all__ = ["create_default_steps", "create_upload_job", "process_import_job"]


def process_import_job(job_id: int) -> None:
    """Verarbeitet einen vorbereiteten Importjob vollständig.

    Extrahiert lokal die PDF-Textschicht und verwendet bei Bedarf den
    konfigurierten OCR-Fallback. Erkannte Laborwerte werden normalisiert,
    innerhalb einer Transaktion gespeichert und bei Unsicherheit als
    Review-Kandidaten markiert.

    Args:
        job_id: Primärschlüssel des zu verarbeitenden Importjobs.

    Raises:
        ImportJob.DoesNotExist: Wenn der Importjob nicht mehr existiert.

    Side Effects:
        Aktualisiert Job- und Pipelinezustände und erzeugt Befunde, Laborwerte,
        Review-Kandidaten, Datengruppen und auditierbare Importlogs. Fachliche
        Verarbeitungsfehler werden am Job gespeichert und nicht weitergereicht.
    """
    job = ImportJob.objects.select_related('patient').get(id=job_id)
    job.status = ImportJob.Status.ANALYZING
    job.progress = 15
    job.pipeline_step = 'Textschicht prüfen'
    job.error_message = ''
    job.recognized_values = 0
    job.uncertain_values = 0
    job.confidence = 0
    job.save(update_fields=['status', 'progress', 'pipeline_step', 'error_message', 'recognized_values', 'uncertain_values', 'confidence', 'updated_at'])
    set_step(job, 'text', ImportStep.Status.ACTIVE, False)

    try:
        result = analyze_pdf(job.source_file.path, ocr_started_callback=lambda: mark_ocr_started(job))
        job.analysis_type = result.analysis_type
        job.ocr_status = ImportJob.OcrStatus.DONE if result.ocr_required and result.text else ImportJob.OcrStatus.NOT_REQUIRED
        if result.ocr_error and not result.text:
            job.ocr_status = ImportJob.OcrStatus.ERROR
        job.progress = 38
        job.pipeline_step = 'Tabellenstruktur erkennen'
        job.save(update_fields=['analysis_type', 'ocr_status', 'progress', 'pipeline_step', 'updated_at'])
        set_step(job, 'text', ImportStep.Status.DONE, True)
        set_step(job, 'ocr', ImportStep.Status.DONE if result.ocr_required and result.text else ImportStep.Status.SKIPPED, True)
        set_step(job, 'table', ImportStep.Status.ACTIVE, False)

        parsed_values = parse_lab_values(result.text)
        if not parsed_values:
            mark_job_error(job, 'Die PDF wurde angenommen, aber es konnten keine Laborwertzeilen erkannt werden. Bitte Testdaten-PDF, Textschicht oder OCR-Setup prüfen.')
            return

        parsed_values, duplicate_count = deduplicate_parsed_values(parsed_values)
        if duplicate_count:
            log(job, 'Doppelte OCR-Treffer bereinigt', f'{duplicate_count} doppelte Laborwert-Treffer wurden zusammengeführt.', 'info')

        patient = job.patient or Patient.objects.order_by('id').first()
        if patient is None:
            raise ValueError('Für den Import ist keine Testperson vorhanden.')

        report_date = extract_report_date(result.text)
        saved_values: list[LabValue] = []
        uncertain_values = 0

        with transaction.atomic():
            set_step(job, 'table', ImportStep.Status.DONE, True)
            set_step(job, 'values', ImportStep.Status.ACTIVE, False)
            report = LabReport.objects.create(public_id=unique_public_id(LabReport, 'befund'), patient=patient, name=job.filename, report_date=report_date, status=LabReport.Status.REVIEW_OPEN, source=job.analysis_type)

            for index, parsed in enumerate(parsed_values, start=1):
                analyte = ensure_analyte(parsed)
                unit = ensure_unit(parsed.unit)
                reference = ensure_reference(analyte, unit, parsed.reference_min, parsed.reference_max)
                value_status = status_for_value(parsed.value, parsed.reference_min, parsed.reference_max, parsed.confidence)
                needs_review = should_review_value(parsed, result.analysis_type, value_status)
                review_status = LabValue.ReviewStatus.REVIEW if needs_review else LabValue.ReviewStatus.CHECKED
                lab_value = save_lab_value(report, analyte, unit, reference, parsed, value_status, review_status)
                saved_values.append(lab_value)

                if review_status == LabValue.ReviewStatus.REVIEW:
                    uncertain_values += 1
                    review_source = ReviewCandidate.Source.OCR if result.analysis_type == ImportJob.AnalysisType.OCR else ReviewCandidate.Source.PDF_TEXT
                    candidate = sync_review_candidate(report, lab_value, analyte, unit, reference, parsed, review_source, index)
                    candidate.parser_hints = review_hints_for_value(parsed, result.analysis_type, value_status)
                    candidate.checks = [
                        {
                            'id': f'check-{index}-wert',
                            'titel': 'Wert prüfen',
                            'beschreibung': 'Bitte Ergebniswert mit dem Originalbefund vergleichen.',
                            'status': 'pruefen',
                        },
                        {
                            'id': f'check-{index}-einheit',
                            'titel': 'Einheit prüfen',
                            'beschreibung': 'Bitte Einheit und Dezimalstellen kontrollieren.',
                            'status': 'pruefen',
                        },
                        {
                            'id': f'check-{index}-referenz',
                            'titel': 'Referenz prüfen',
                            'beschreibung': 'Bitte Referenzbereich aus dem Befund bestätigen.',
                            'status': 'pruefen',
                        },
                    ]
                    candidate.save(update_fields=['parser_hints', 'checks', 'updated_at'])

            job.recognized_values = len(saved_values)
            job.uncertain_values = uncertain_values
            job.confidence = round(mean(item.confidence for item in saved_values)) if saved_values else 0
            job.progress = 100
            job.status = ImportJob.Status.REVIEW if job.uncertain_values else ImportJob.Status.DONE
            job.pipeline_step = 'Review vorbereitet' if job.uncertain_values else 'Import abgeschlossen'
            job.error_message = ''
            job.save(update_fields=['recognized_values', 'uncertain_values', 'confidence', 'progress', 'status', 'pipeline_step', 'error_message', 'updated_at'])
            ImportDataset.objects.filter(job=job).delete()
            create_datasets(job, saved_values)
            set_step(job, 'values', ImportStep.Status.DONE, True)
            set_step(job, 'confidence', ImportStep.Status.DONE, True)

        log(job, f'{job.recognized_values} Werte erkannt', f'{job.uncertain_values} Werte wurden für den Review markiert. Befund wurde {patient.display_name} zugeordnet.', job.status)
    except Exception as exc:
        job = ImportJob.objects.get(id=job_id)
        job.status = ImportJob.Status.ERROR
        job.progress = max(job.progress, 20)
        job.pipeline_step = 'Importfehler'
        job.error_message = str(exc)
        job.save(update_fields=['status', 'progress', 'pipeline_step', 'error_message', 'updated_at'])
        set_step(job, 'values', ImportStep.Status.ERROR, False)
        log(job, 'Importfehler', str(exc), ImportJob.Status.ERROR)
