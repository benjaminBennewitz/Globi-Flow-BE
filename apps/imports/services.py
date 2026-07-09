# apps/imports/services.py

"""Importservice für Uploads, lokale Analyse und Persistenz."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
import re
from statistics import mean
from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from apps.core.utils import public_id
from apps.imports.models import ImportDataset, ImportJob, ImportLog, ImportStep
from apps.imports.parser import ParsedLabValue, parse_lab_values
from apps.imports.pdf_analysis import analyze_pdf
from apps.labs.models import LabAnalyte, LabGroup, LabReport, LabUnit, LabValue, ReferenceRange, ReviewCandidate
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
    job = ImportJob.objects.create(public_id=unique_public_id(ImportJob, 'import', next_number), patient=patient, filename=uploaded_file.name, test_person_label=patient.display_name if patient else 'nicht zugeordnet')
    job.source_file.save(uploaded_file.name, uploaded_file, save=True)
    create_default_steps(job)
    set_step(job, 'upload', ImportStep.Status.DONE, True)
    log(job, 'Upload validiert', 'PDF wurde lokal angenommen.', ImportJob.Status.WAITING)
    return job


def slugify_key(value: str, fallback: str = 'wert') -> str:
    """Erzeugt einen stabilen DB-Key ohne Umlaut-Dubletten."""
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', 'µ': 'u'}
    result = str(value or fallback).strip().lower()
    for source, target in replacements.items():
        result = result.replace(source, target)
    result = '_'.join(''.join(char if char.isalnum() else ' ' for char in result).split())
    return result or fallback


def unique_public_id(model, prefix: str, start: int | None = None) -> str:
    """Erzeugt eine öffentliche ID ohne Kollision nach Demo-Resets oder Löschungen."""
    next_number = start or ((model.objects.aggregate(max_id=Max('id'))['max_id'] or 0) + 1)
    candidate = public_id(prefix, next_number)
    while model.objects.filter(public_id=candidate).exists():
        next_number += 1
        candidate = public_id(prefix, next_number)
    return candidate


def set_step(job: ImportJob, key: str, status: str, is_completed: bool = False) -> None:
    """Aktualisiert einen Pipeline-Schritt, ohne bei fehlendem Schritt abzubrechen."""
    ImportStep.objects.filter(job=job, key=key).update(status=status, is_completed=is_completed, updated_at=timezone.now())


def ensure_group(group_name: str) -> LabGroup:
    """Lädt oder erstellt eine Laborgruppe anhand von Key oder Name."""
    safe_name = str(group_name or 'Importierte Werte').strip() or 'Importierte Werte'
    safe_key = slugify_key(safe_name, 'importierte_werte')
    group = LabGroup.objects.filter(Q(key=safe_key) | Q(name__iexact=safe_name)).order_by('id').first()
    if group:
        return group
    return LabGroup.objects.create(key=safe_key, name=safe_name)


def ensure_unit(code: str) -> LabUnit:
    """Lädt oder erstellt eine Laborwert-Einheit."""
    clean_code = str(code or '').strip() or 'ohne Einheit'
    unit, _ = LabUnit.objects.get_or_create(code=clean_code, defaults={'normalized_code': clean_code.lower()})
    return unit


def ensure_analyte(parsed: ParsedLabValue) -> LabAnalyte:
    """Lädt oder erstellt einen Laborwert aus Parserdaten."""
    safe_key = slugify_key(parsed.analyte_key or parsed.display_name, 'laborwert')
    existing = LabAnalyte.objects.select_related('group').filter(key=safe_key).first()
    if existing:
        changed_fields = []
        if parsed.display_name and existing.display_name != parsed.display_name:
            existing.display_name = parsed.display_name
            changed_fields.append('display_name')
        aliases = set(existing.aliases or [])
        aliases.update({parsed.display_name, safe_key.replace('_', ' ')})
        if sorted(aliases) != sorted(existing.aliases or []):
            existing.aliases = sorted(aliases)
            changed_fields.append('aliases')
        if changed_fields:
            existing.save(update_fields=[*changed_fields, 'updated_at'])
        return existing

    group = ensure_group(parsed.group_name)
    return LabAnalyte.objects.create(key=safe_key, display_name=parsed.display_name or safe_key, group=group, aliases=[parsed.display_name, safe_key.replace('_', ' ')])


def ensure_reference(analyte: LabAnalyte, unit: LabUnit, lower: Decimal, upper: Decimal) -> ReferenceRange:
    """Erstellt oder lädt einen passenden Referenzbereich."""
    reference, _ = ReferenceRange.objects.get_or_create(analyte=analyte, unit=unit, sex=ReferenceRange.Sex.ANY, age_min=None, age_max=None, lower=lower, upper=upper, defaults={'source_note': 'Importiert aus lokalem Befund'})
    return reference


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


def parse_report_date_value(value: str) -> date | None:
    """Wandelt erkannte Datumswerte aus Laborbefunden in ein Datum um."""
    clean = str(value or '').strip()
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', clean):
            return date.fromisoformat(clean)
        if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', clean):
            day, month, year = clean.split('.')
            return date(int(year), int(month), int(day))
    except ValueError:
        return None
    return None


def extract_report_date(text: str) -> date:
    """Liest das Befunddatum aus Textschicht- und OCR-Laborbefunden."""
    compact_text = re.sub(r'\s+', ' ', text or '')
    patterns = [
        r'Befunddatum\s+(?P<date>\d{4}-\d{2}-\d{2})',
        r'Befunddatum\s+(?P<date>\d{2}\.\d{2}\.\d{4})',
        r'Eingangsdatum:?\s+(?P<date>\d{2}\.\d{2}\.\d{4})',
        r'Endbefund\s+(?P<date>\d{2}\.\d{2}\.\d{4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, compact_text, flags=re.IGNORECASE)
        if not match:
            continue
        parsed_date = parse_report_date_value(match.group('date'))
        if parsed_date:
            return parsed_date

    fallback_match = re.search(r'(?P<date>\d{2}\.\d{2}\.\d{4})', compact_text)
    if fallback_match:
        parsed_date = parse_report_date_value(fallback_match.group('date'))
        if parsed_date:
            return parsed_date

    return timezone.localdate()


def mark_job_error(job: ImportJob, message: str) -> None:
    """Schließt einen Importjob kontrolliert als Fehler ab."""
    set_step(job, 'values', ImportStep.Status.ERROR, False)
    job.status = ImportJob.Status.ERROR
    job.progress = 100
    job.pipeline_step = 'Keine Laborwerte erkannt'
    job.error_message = message
    job.recognized_values = 0
    job.uncertain_values = 0
    job.confidence = 0
    job.save(update_fields=['status', 'progress', 'pipeline_step', 'error_message', 'recognized_values', 'uncertain_values', 'confidence', 'updated_at'])
    log(job, 'Keine Werte erkannt', message, ImportJob.Status.ERROR)


def mark_ocr_started(job: ImportJob) -> None:
    """Markiert einen Importjob sichtbar als laufenden OCR-Prozess."""
    job.status = ImportJob.Status.ANALYZING
    job.ocr_status = ImportJob.OcrStatus.ACTIVE
    job.progress = max(job.progress, 24)
    job.pipeline_step = 'Lokale OCR läuft'
    job.recognized_values = 0
    job.uncertain_values = 0
    job.confidence = 0
    job.save(update_fields=['status', 'ocr_status', 'progress', 'pipeline_step', 'recognized_values', 'uncertain_values', 'confidence', 'updated_at'])
    set_step(job, 'text', ImportStep.Status.DONE, True)
    set_step(job, 'ocr', ImportStep.Status.ACTIVE, False)
    log(job, 'OCR gestartet', 'Keine verwertbare Textschicht gefunden. Tesseract verarbeitet die PDF lokal.', 'info')


def create_datasets(job: ImportJob, saved_values: list[LabValue]) -> None:
    """Erstellt gruppierte Import-Datasets für die UI."""
    grouped: dict[str, list[LabValue]] = defaultdict(list)
    for lab_value in saved_values:
        grouped[lab_value.analyte.group.name].append(lab_value)

    for index, (group_name, values) in enumerate(sorted(grouped.items()), start=1):
        review_count = sum(1 for value in values if value.review_status == LabValue.ReviewStatus.REVIEW)
        confidence = round(mean(value.confidence for value in values)) if values else 0
        ImportDataset.objects.create(public_id=f'dataset-{job.public_id}-{index}', job=job, name=group_name, values_count=len(values), review_count=review_count, confidence=confidence, status=ImportDataset.Status.REVIEW if review_count else ImportDataset.Status.NORMAL)



def deduplicate_parsed_values(parsed_values: list[ParsedLabValue]) -> tuple[list[ParsedLabValue], int]:
    """Entfernt doppelte OCR-Treffer je Laborwert innerhalb eines Befunds."""
    unique_values: dict[str, ParsedLabValue] = {}
    duplicate_count = 0

    for parsed in parsed_values:
        key = slugify_key(parsed.analyte_key or parsed.display_name, 'laborwert')
        existing = unique_values.get(key)

        if existing is None:
            unique_values[key] = parsed
            continue

        duplicate_count += 1
        should_replace = parsed.confidence > existing.confidence
        same_confidence_newer_text = parsed.confidence == existing.confidence and len(parsed.original_text) > len(existing.original_text)

        if should_replace or same_confidence_newer_text:
            unique_values[key] = parsed

    return list(unique_values.values()), duplicate_count





def auto_review_threshold() -> int:
    """Liefert den konfigurierbaren Confidence-Grenzwert für automatische Übernahme."""
    return int(getattr(settings, 'IMPORT_AUTO_REVIEW_CONFIDENCE_THRESHOLD', 90))

def review_hints_for_value(parsed: ParsedLabValue, analysis_type: str, value_status: str) -> list[str]:
    """Ermittelt nachvollziehbare Review-Hinweise für importierte Laborwerte."""
    hints: list[str] = []

    threshold = auto_review_threshold()

    if analysis_type == ImportJob.AnalysisType.OCR and parsed.confidence < threshold:
        hints.append(f'OCR-Import unter {threshold} Prozent Confidence.')
    if value_status == LabValue.Status.REVIEW:
        hints.append('Confidence liegt unter dem Grenzwert für automatische Übernahme.')
    if parsed.confidence < threshold:
        hints.append(f'Erkennungsqualität unter {threshold} Prozent.')
    if not str(parsed.unit or '').strip() or str(parsed.unit or '').strip().lower() == 'ohne einheit':
        hints.append('Einheit konnte nicht sicher erkannt werden.')
    if parsed.reference_min == parsed.reference_max:
        hints.append('Referenzbereich wirkt unvollständig oder unsicher.')

    return hints or ['Automatisch markiert, weil Alias oder Confidence ärztlich geprüft werden sollte.']


def should_review_value(parsed: ParsedLabValue, analysis_type: str, value_status: str) -> bool:
    """Entscheidet, ob ein erkannter Wert in den Review muss."""
    threshold = auto_review_threshold()

    if value_status == LabValue.Status.REVIEW:
        return True
    if parsed.confidence < threshold:
        return True
    if not str(parsed.unit or '').strip() or str(parsed.unit or '').strip().lower() == 'ohne einheit':
        return True
    if parsed.reference_min == parsed.reference_max:
        return True
    return False


def save_lab_value(report: LabReport, analyte: LabAnalyte, unit: LabUnit, reference: ReferenceRange, parsed: ParsedLabValue, value_status: str, review_status: str) -> LabValue:
    """Speichert einen Laborwert idempotent für Befund und Laborwert-Key."""
    lab_value, created = LabValue.objects.update_or_create(
        report=report,
        analyte=analyte,
        defaults={
            'public_id': unique_public_id(LabValue, 'wert'),
            'unit': unit,
            'reference_range': reference,
            'value': parsed.value,
            'status': value_status,
            'priority': priority_for_status(value_status),
            'review_status': review_status,
            'confidence': parsed.confidence,
            'hint': 'Aus lokalem Import erkannt.',
            'original_text': parsed.original_text,
        },
    )

    if not created and not lab_value.public_id:
        lab_value.public_id = unique_public_id(LabValue, 'wert')
        lab_value.save(update_fields=['public_id', 'updated_at'])

    return lab_value


def sync_review_candidate(report: LabReport, lab_value: LabValue, analyte: LabAnalyte, unit: LabUnit, reference: ReferenceRange, parsed: ParsedLabValue, source: str, index: int) -> ReviewCandidate:
    """Legt einen Review-Kandidaten an oder aktualisiert den bestehenden Kandidaten."""
    candidate = ReviewCandidate.objects.filter(report=report, analyte=analyte, source=source).exclude(status=ReviewCandidate.Status.DISCARDED).order_by('id').first()
    defaults = {
        'lab_value': lab_value,
        'raw_name': parsed.display_name,
        'raw_value': str(parsed.value),
        'corrected_value': parsed.value,
        'raw_unit': parsed.unit,
        'corrected_unit': unit,
        'reference_range': reference,
        'original_text': parsed.original_text,
        'original_label': f'Importzeile {index}',
        'confidence': parsed.confidence,
        'parser_hints': ['Automatisch markiert, weil Alias oder Confidence ärztlich geprüft werden sollte.'],
        'checks': [{'id': f'check-{index}', 'titel': 'Parserprüfung', 'beschreibung': 'Bitte Wert, Einheit und Referenzbereich bestätigen.', 'status': 'pruefen'}],
    }

    if candidate:
        for field, value in defaults.items():
            setattr(candidate, field, value)
        if candidate.status not in {ReviewCandidate.Status.CORRECTED, ReviewCandidate.Status.CONFIRMED}:
            candidate.status = ReviewCandidate.Status.OPEN
        candidate.save(update_fields=[*defaults.keys(), 'status', 'updated_at'])
        return candidate

    return ReviewCandidate.objects.create(public_id=unique_public_id(ReviewCandidate, 'review'), report=report, analyte=analyte, source=source, **defaults)


def process_import_job(job_id: int) -> None:
    """Analysiert einen Importjob lokal und persistiert erkannte Werte."""
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
