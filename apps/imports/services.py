# apps/imports/services.py

"""Importservice für Uploads, lokale Analyse und Persistenz."""

from decimal import Decimal
from statistics import mean
from django.db import transaction
from django.utils import timezone
from apps.core.utils import public_id
from apps.imports.models import ImportDataset, ImportJob, ImportLog, ImportStep
from apps.imports.parser import parse_lab_values
from apps.imports.pdf_analysis import analyze_pdf
from apps.labs.models import LabGroup, LabAnalyte, LabReport, LabUnit, LabValue, ReferenceRange, ReviewCandidate
from apps.patients.models import Patient

PIPELINE_STEPS = [
    ('upload', 'Upload geprüft', 'Datei wurde validiert und lokal gespeichert.'),
    ('text', 'Textschicht gelesen', 'PDF-Textschicht wurde lokal extrahiert.'),
    ('ocr', 'OCR-Fallback geprüft', 'OCR wurde nur bei fehlender Textschicht genutzt.'),
    ('table', 'Tabellen erkannt', 'Tabellenstruktur wurde für die Extraktion vorbereitet.'),
    ('values', 'Werte extrahiert', 'Laborwerte, Einheiten und Referenzen wurden erkannt.'),
    ('confidence', 'Confidence berechnet', 'Unsichere Werte wurden für Review markiert.'),
]


def create_default_steps(job: ImportJob) -> None:
    """Legt Standard-Pipelineschritte an."""
    for index, (key, name, description) in enumerate(PIPELINE_STEPS, start=1):
        ImportStep.objects.create(job=job, key=key, name=name, description=description, status=ImportStep.Status.WAITING, sort_order=index)


def log(job: ImportJob, title: str, description: str, status: str = 'info') -> None:
    """Schreibt einen Importlogeintrag."""
    count = job.logs.count() + 1
    ImportLog.objects.create(public_id=f'log-{job.id}-{count}', job=job, time_label=timezone.localtime().strftime('%H:%M'), title=title, description=description, status=status)


def create_upload_job(uploaded_file, patient: Patient | None = None) -> ImportJob:
    """Erstellt einen Importjob für einen validierten Upload."""
    next_number = ImportJob.objects.count() + 1
    job = ImportJob.objects.create(public_id=public_id('import', next_number), patient=patient, filename=uploaded_file.name, test_person_label=patient.display_name if patient else 'nicht zugeordnet')
    job.source_file.save(uploaded_file.name, uploaded_file, save=True)
    create_default_steps(job)
    log(job, 'Upload validiert', 'PDF wurde lokal angenommen.', ImportJob.Status.WAITING)
    return job


def status_for_value(value: Decimal, lower: Decimal, upper: Decimal, confidence: int) -> str:
    """Berechnet den Darstellungsstatus eines Werts."""
    if confidence < 75:
        return LabValue.Status.REVIEW
    if value < lower:
        return LabValue.Status.LOW
    if value > upper:
        return LabValue.Status.HIGH
    return LabValue.Status.NORMAL


def priority_for_status(status: str) -> str:
    """Leitet eine einfache Anzeigepriorität ab."""
    if status == LabValue.Status.HIGH:
        return LabValue.Priority.HIGH
    if status in {LabValue.Status.LOW, LabValue.Status.REVIEW}:
        return LabValue.Priority.MEDIUM
    return LabValue.Priority.LOW


def ensure_reference(analyte: LabAnalyte, unit: LabUnit, lower: Decimal, upper: Decimal) -> ReferenceRange:
    """Erstellt oder lädt einen passenden Referenzbereich."""
    reference, _ = ReferenceRange.objects.get_or_create(analyte=analyte, unit=unit, sex=ReferenceRange.Sex.ANY, age_min=None, age_max=None, lower=lower, upper=upper, defaults={'source_note': 'Importiert aus lokalem Befund'})
    return reference


@transaction.atomic
def process_import_job(job_id: int) -> None:
    """Analysiert einen Importjob lokal und persistiert erkannte Werte."""
    job = ImportJob.objects.select_for_update().get(id=job_id)
    job.status = ImportJob.Status.ANALYZING
    job.progress = 15
    job.pipeline_step = 'Lokale Textanalyse'
    job.save(update_fields=['status', 'progress', 'pipeline_step', 'updated_at'])

    try:
        result = analyze_pdf(job.source_file.path)
        job.analysis_type = result.analysis_type
        job.ocr_status = ImportJob.OcrStatus.DONE if result.ocr_required and result.text else ImportJob.OcrStatus.NOT_REQUIRED
        if result.ocr_error and not result.text:
            job.ocr_status = ImportJob.OcrStatus.ERROR
        parsed_values = parse_lab_values(result.text)
        patient = job.patient or Patient.objects.order_by('id').first()
        if patient is None:
            raise ValueError('Für den Import ist keine Testperson vorhanden.')

        report = LabReport.objects.create(public_id=public_id('befund', LabReport.objects.count() + 1), patient=patient, name=job.filename, report_date=timezone.localdate(), status=LabReport.Status.REVIEW_OPEN, source=job.analysis_type)
        saved_values = []
        for index, parsed in enumerate(parsed_values, start=1):
            group, _ = LabGroup.objects.get_or_create(key=parsed.group_name.lower().replace(' ', '_'), defaults={'name': parsed.group_name})
            analyte, _ = LabAnalyte.objects.get_or_create(key=parsed.analyte_key, defaults={'display_name': parsed.display_name, 'group': group})
            unit, _ = LabUnit.objects.get_or_create(code=parsed.unit, defaults={'normalized_code': parsed.unit.lower()})
            reference = ensure_reference(analyte, unit, parsed.reference_min, parsed.reference_max)
            status = status_for_value(parsed.value, parsed.reference_min, parsed.reference_max, parsed.confidence)
            lab_value = LabValue.objects.create(public_id=public_id('wert', LabValue.objects.count() + 1), report=report, analyte=analyte, unit=unit, reference_range=reference, value=parsed.value, status=status, priority=priority_for_status(status), review_status='review' if status == 'review' else 'geprueft', confidence=parsed.confidence, hint='Aus lokalem Import erkannt.', original_text=parsed.original_text)
            saved_values.append(lab_value)
            if status == LabValue.Status.REVIEW:
                ReviewCandidate.objects.create(public_id=public_id('review', ReviewCandidate.objects.count() + 1), report=report, lab_value=lab_value, analyte=analyte, raw_name=parsed.display_name, raw_value=str(parsed.value), corrected_value=parsed.value, raw_unit=parsed.unit, corrected_unit=unit, reference_range=reference, original_text=parsed.original_text, original_label=f'Importzeile {index}', confidence=parsed.confidence, source=ReviewCandidate.Source.OCR if result.analysis_type == 'ocr' else ReviewCandidate.Source.PDF_TEXT, parser_hints=['Automatisch markiert, weil Confidence unter 75 liegt.'], checks=[{'id': f'check-{index}', 'titel': 'Confidence', 'beschreibung': 'Bitte Wert und Einheit prüfen.', 'status': 'pruefen'}])

        job.recognized_values = len(saved_values)
        job.uncertain_values = sum(1 for item in saved_values if item.status == LabValue.Status.REVIEW)
        job.confidence = round(mean(item.confidence for item in saved_values)) if saved_values else 0
        job.progress = 100
        job.status = ImportJob.Status.REVIEW if job.uncertain_values else ImportJob.Status.DONE
        job.pipeline_step = 'Review vorbereitet' if job.uncertain_values else 'Import abgeschlossen'
        job.save()
        ImportDataset.objects.create(public_id=f'dataset-{job.id}-gesamt', job=job, name='Erkannte Laborwerte', values_count=job.recognized_values, review_count=job.uncertain_values, confidence=job.confidence, status=ImportDataset.Status.REVIEW if job.uncertain_values else ImportDataset.Status.NORMAL)
        job.steps.update(status=ImportStep.Status.DONE, is_completed=True)
        log(job, f'{job.recognized_values} Werte erkannt', f'{job.uncertain_values} Werte wurden für den Review markiert.', job.status)
    except Exception as exc:
        job.status = ImportJob.Status.ERROR
        job.progress = max(job.progress, 20)
        job.pipeline_step = 'Importfehler'
        job.error_message = str(exc)
        job.save(update_fields=['status', 'progress', 'pipeline_step', 'error_message', 'updated_at'])
        log(job, 'Importfehler', str(exc), ImportJob.Status.ERROR)
        raise
