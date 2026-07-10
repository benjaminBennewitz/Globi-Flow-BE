# apps/imports/service_setup.py

"""Erzeugt Importjobs, Stammdaten und technische Pipelinezustände."""

from datetime import date
from decimal import Decimal
import re
from django.db.models import Max, Q
from django.utils import timezone
from apps.core.utils import public_id
from apps.imports.models import ImportJob, ImportLog, ImportStep
from apps.imports.parser import ParsedLabValue
from apps.labs.models import LabAnalyte, LabGroup, LabUnit, LabValue, ReferenceRange
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
