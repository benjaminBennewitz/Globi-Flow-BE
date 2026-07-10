# apps/imports/view_helpers.py

"""Hilfsfunktionen für Import- und Review-API-Views."""

from decimal import Decimal, InvalidOperation

from django.db.models import Q

from apps.imports.models import ImportJob
from apps.labs.models import LabAnalyte, LabGroup, LabReport, LabUnit, LabValue, ReferenceRange, ReviewCandidate


def to_decimal(value, fallback=Decimal('0')) -> Decimal:
    """Wandelt API-Eingaben robust in Decimal um.

    Args:
        value: Zu verarbeitender Eingabewert.
        fallback: Wert für ``fallback``.

    Returns:
        Rückgabewert vom Typ ``Decimal``.
    """
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, TypeError, ValueError):
        return fallback


def import_job_queryset():
    """Lädt Importjobs mit allen Statusrelationen.
    """
    return ImportJob.objects.select_related('patient').prefetch_related('steps', 'datasets', 'logs')


def ensure_unit(code: str) -> LabUnit:
    """Lädt oder erstellt eine Laborwert-Einheit.

    Args:
        code: Wert für ``code``.

    Returns:
        Rückgabewert vom Typ ``LabUnit``.
    """
    clean_code = str(code or '').strip() or 'ohne Einheit'
    unit, _ = LabUnit.objects.get_or_create(code=clean_code, defaults={'normalized_code': clean_code.lower()})
    return unit


def slugify_key(value: str, fallback: str = 'wert') -> str:
    """Erzeugt einen DB-stabilen Schlüssel ohne Umlaut-Dubletten.

    Args:
        value: Zu verarbeitender Eingabewert.
        fallback: Wert für ``fallback``.

    Returns:
        Rückgabewert vom Typ ``str``.
    """
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'}
    result = str(value or fallback).strip().lower()
    for source, target in replacements.items():
        result = result.replace(source, target)
    result = '_'.join(''.join(char if char.isalnum() else ' ' for char in result).split())
    return result or fallback


def ensure_group(group_name: str = 'Manuelle Werte') -> LabGroup:
    """Lädt oder erstellt eine Laborgruppe ohne Unique-Konflikte über Namen.

    Args:
        group_name: Wert für ``group_name``.

    Returns:
        Rückgabewert vom Typ ``LabGroup``.
    """
    safe_name = str(group_name or 'Manuelle Werte').strip() or 'Manuelle Werte'
    safe_key = slugify_key(safe_name, 'manuelle_werte')
    group = LabGroup.objects.filter(Q(key=safe_key) | Q(name__iexact=safe_name)).order_by('id').first()
    if group:
        return group
    return LabGroup.objects.create(key=safe_key, name=safe_name)


def ensure_analyte(key: str, display_name: str, group_name: str = 'Manuelle Werte') -> LabAnalyte:
    """Lädt oder erstellt einen Laborwert inklusive Gruppe.

    Args:
        key: Stabiler fachlicher oder technischer Schlüssel.
        display_name: Wert für ``display_name``.
        group_name: Wert für ``group_name``.

    Returns:
        Rückgabewert vom Typ ``LabAnalyte``.
    """
    safe_name = str(display_name or key or 'Manueller Laborwert').strip() or 'Manueller Laborwert'
    safe_key = slugify_key(key or safe_name, 'manueller_laborwert')
    group = ensure_group(group_name)
    analyte, _ = LabAnalyte.objects.get_or_create(key=safe_key, defaults={'display_name': safe_name, 'group': group, 'aliases': [safe_name, safe_key.replace('_', ' ')]})
    changed_fields = []
    if analyte.display_name != safe_name:
        analyte.display_name = safe_name
        changed_fields.append('display_name')
    if analyte.group_id != group.id:
        analyte.group = group
        changed_fields.append('group')
    if changed_fields:
        analyte.save(update_fields=[*changed_fields, 'updated_at'])
    return analyte


def ensure_reference(analyte: LabAnalyte, unit: LabUnit, lower: Decimal, upper: Decimal) -> ReferenceRange:
    """Lädt oder erstellt einen Referenzbereich.

    Args:
        analyte: Wert für ``analyte``.
        unit: Wert für ``unit``.
        lower: Wert für ``lower``.
        upper: Wert für ``upper``.

    Returns:
        Rückgabewert vom Typ ``ReferenceRange``.
    """
    reference, _ = ReferenceRange.objects.get_or_create(analyte=analyte, unit=unit, sex=ReferenceRange.Sex.ANY, age_min=None, age_max=None, lower=lower, upper=upper, defaults={'source_note': 'Manuell oder Review gepflegt'})
    return reference


def status_for_value(value: Decimal, lower: Decimal, upper: Decimal, confidence: int = 100) -> str:
    """Berechnet den Wertstatus anhand des Referenzbereichs.

    Args:
        value: Zu verarbeitender Eingabewert.
        lower: Wert für ``lower``.
        upper: Wert für ``upper``.
        confidence: Wert für ``confidence``.

    Returns:
        Rückgabewert vom Typ ``str``.
    """
    if confidence < 75:
        return LabValue.Status.REVIEW
    if value < lower:
        return LabValue.Status.LOW
    if value > upper:
        return LabValue.Status.HIGH
    return LabValue.Status.NORMAL


def priority_for_status(value_status: str) -> str:
    """Leitet eine Anzeigepriorität aus dem Wertstatus ab.

    Args:
        value_status: Wert für ``value_status``.

    Returns:
        Rückgabewert vom Typ ``str``.
    """
    if value_status == LabValue.Status.HIGH:
        return LabValue.Priority.HIGH
    if value_status in {LabValue.Status.LOW, LabValue.Status.REVIEW}:
        return LabValue.Priority.MEDIUM
    return LabValue.Priority.LOW


def refresh_report_review_status(report: LabReport) -> None:
    """Aktualisiert den Befundstatus nach Review-Änderungen.

    Args:
        report: Betroffener Labor- oder Patientenbericht.
    """
    has_open_candidates = report.review_candidates.filter(status__in=[ReviewCandidate.Status.OPEN, ReviewCandidate.Status.BLOCKED]).exists()
    has_review_values = report.values.filter(review_status=LabValue.ReviewStatus.REVIEW).exists()
    if has_open_candidates or has_review_values:
        next_status = LabReport.Status.REVIEW_OPEN
    elif report.status == LabReport.Status.RELEASED:
        next_status = LabReport.Status.RELEASED
    else:
        next_status = LabReport.Status.REPORT_READY
    if report.status != next_status:
        report.status = next_status
        report.save(update_fields=['status', 'updated_at'])


def parse_reference_range(raw_value: str) -> tuple[Decimal, Decimal]:
    """Liest einfache Referenzbereiche wie 4.0-10.0 ein.

    Args:
        raw_value: Wert für ``raw_value``.

    Returns:
        Rückgabewert vom Typ ``tuple[Decimal, Decimal]``.
    """
    clean_value = str(raw_value or '').replace('–', '-').replace(',', '.')
    parts = [part.strip() for part in clean_value.split('-', maxsplit=1)]
    if len(parts) != 2:
        return Decimal('0'), Decimal('999999')
    return to_decimal(parts[0]), to_decimal(parts[1], Decimal('999999'))


