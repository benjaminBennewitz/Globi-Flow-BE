# apps/labs/presenters.py

"""Präsentationsfunktionen für Laborwerte im Angular-Format."""

from decimal import Decimal
from statistics import mean
from apps.core.utils import decimal_to_number, format_date
from apps.labs.models import LabReport, LabValue, ReviewCandidate
from apps.knowledge.services import color_for_key, normalize_chart_color


def analyte_chart_color(value: LabValue) -> str:
    """Liefert die Wissensbasis-Farbe eines Laborwerts oder einen stabilen Fallback."""
    try:
        return normalize_chart_color(value.analyte.knowledge_entry.chart_color, value.analyte.key)
    except Exception:
        return color_for_key(value.analyte.key)


def trend_direction(current: Decimal, previous: Decimal | None) -> str:
    """Berechnet eine einfache Trendrichtung."""
    if previous is None:
        return 'stabil'
    if current > previous:
        return 'steigend'
    if current < previous:
        return 'fallend'
    return 'stabil'


def previous_value(value: LabValue) -> LabValue | None:
    """Findet den vorherigen Wert desselben Laborparameters."""
    return LabValue.objects.filter(report__patient=value.report.patient, analyte=value.analyte, report__report_date__lt=value.report.report_date).exclude(report__values__isnull=True).select_related('report').order_by('-report__report_date').first()


def value_history(value: LabValue) -> list[LabValue]:
    """Lädt den Verlauf eines Laborparameters für die aktuelle Testperson."""
    return list(LabValue.objects.filter(report__patient=value.report.patient, analyte=value.analyte).select_related('report').order_by('report__report_date'))


def lab_value_to_dashboard(value: LabValue) -> dict:
    """Gibt einen Laborwert als kompaktes Dashboard-Objekt aus."""
    history = value_history(value)
    return {
        'id': value.public_id,
        'key': value.analyte.key,
        'name': value.analyte.display_name,
        'gruppe': value.analyte.group.name,
        'wert': decimal_to_number(value.value),
        'einheit': value.unit.code,
        'referenzMin': decimal_to_number(value.reference_range.lower),
        'referenzMax': decimal_to_number(value.reference_range.upper),
        'status': value.status,
        'farbe': analyte_chart_color(value),
        'prioritaet': value.priority,
        'confidence': value.confidence,
        'trend': [decimal_to_number(entry.value) for entry in history][-5:],
        'hinweis': value.hint,
    }


def lab_value_to_evaluation(value: LabValue) -> dict:
    """Gibt einen Laborwert für die Auswertungsroute aus."""
    previous = previous_value(value)
    has_previous = previous is not None
    previous_number = previous.value if previous else value.value
    change_abs = value.value - previous_number if has_previous else Decimal('0')
    change_pct = Decimal('0') if not has_previous or previous_number == 0 else (change_abs / previous_number) * Decimal('100')
    limit = value.reference_range.upper if value.status == LabValue.Status.HIGH else value.reference_range.lower
    deviation = Decimal('0')
    if limit and limit != 0 and value.status in {LabValue.Status.HIGH, LabValue.Status.LOW, LabValue.Status.REVIEW}:
        deviation = abs(value.value - limit) / limit * Decimal('100')

    return {
        'id': value.public_id,
        'key': value.analyte.key,
        'name': value.analyte.display_name,
        'gruppe': value.analyte.group.name,
        'wert': decimal_to_number(value.value),
        'vorherigerWert': decimal_to_number(previous_number),
        'hatVergleich': has_previous,
        'einheit': value.unit.code,
        'referenzMin': decimal_to_number(value.reference_range.lower),
        'referenzMax': decimal_to_number(value.reference_range.upper),
        'status': value.status,
        'farbe': analyte_chart_color(value),
        'prioritaet': value.priority,
        'reviewStatus': value.review_status,
        'confidence': value.confidence,
        'veraenderungAbsolut': decimal_to_number(change_abs),
        'veraenderungProzent': round(float(change_pct)),
        'abweichungProzent': round(float(deviation)),
        'trend': trend_direction(value.value, previous.value if previous else None),
        'hinweis': value.hint,
        'verlauf': [{'label': entry.report.report_date.strftime('%b %y'), 'datum': entry.report.report_date.isoformat(), 'wert': decimal_to_number(entry.value)} for entry in value_history(value)][-6:],
    }


def group_summary(values: list[LabValue], detailed: bool = False) -> list[dict]:
    """Berechnet gruppierte Statuszahlen."""
    groups = {}
    for value in values:
        key = value.analyte.group.key
        group = groups.setdefault(key, {'key': key, 'name': value.analyte.group.name, 'normal': 0, 'auffaellig': 0, 'review': 0, 'niedrig': 0, 'hoch': 0})
        if value.status == LabValue.Status.NORMAL:
            group['normal'] += 1
        elif value.status == LabValue.Status.REVIEW:
            group['review'] += 1
        elif value.status == LabValue.Status.LOW:
            group['niedrig'] += 1
            group['auffaellig'] += 1
        elif value.status == LabValue.Status.HIGH:
            group['hoch'] += 1
            group['auffaellig'] += 1

    result = list(groups.values())
    if detailed:
        return [{'key': item['key'], 'name': item['name'], 'normal': item['normal'], 'niedrig': item['niedrig'], 'hoch': item['hoch'], 'review': item['review']} for item in result]
    return [{'key': item['key'], 'name': item['name'], 'normal': item['normal'], 'auffaellig': item['auffaellig'], 'review': item['review']} for item in result]


def trend_series(values: list[LabValue]) -> list[dict]:
    """Erzeugt Dashboard-Trendserien für auffällige oder wichtige Werte."""
    selected = sorted(values, key=lambda item: (item.priority != 'hoch', item.status == 'normal', item.analyte.display_name))[:4]
    return [
        {
            'key': value.analyte.key,
            'name': value.analyte.display_name,
            'einheit': value.unit.code,
            'farbe': analyte_chart_color(value),
            'werte': [decimal_to_number(entry.value) for entry in value_history(value)][-6:],
            'referenzMin': decimal_to_number(value.reference_range.lower),
            'referenzMax': decimal_to_number(value.reference_range.upper),
        }
        for value in selected
    ]


def review_candidate_to_frontend(candidate: ReviewCandidate) -> dict:
    """Gibt einen Review-Kandidaten im vollständigen Review-ViewModel aus."""
    return {
        'id': candidate.public_id,
        'patientId': candidate.report.patient.public_id,
        'befundId': candidate.report.public_id,
        'laborwertKey': candidate.analyte.key,
        'anzeigename': candidate.analyte.display_name,
        'erkannterName': candidate.raw_name,
        'erkannterWert': candidate.raw_value,
        'korrigierterWert': decimal_to_number(candidate.corrected_value),
        'erkannteEinheit': candidate.raw_unit,
        'korrigierteEinheit': candidate.corrected_unit.code,
        'referenzMin': decimal_to_number(candidate.reference_range.lower),
        'referenzMax': decimal_to_number(candidate.reference_range.upper),
        'originalText': candidate.original_text,
        'originalLabel': candidate.original_label,
        'confidence': candidate.confidence,
        'status': candidate.status,
        'gruppe': candidate.analyte.group.name,
        'quelle': candidate.source,
        'kommentar': candidate.comment,
        'parserHinweise': candidate.parser_hints,
        'checks': candidate.checks,
    }


def review_entry_to_frontend(candidate: ReviewCandidate) -> dict:
    """Gibt den kompakten Review-Eintrag für die Startansicht aus."""
    return {
        'id': candidate.public_id,
        'laborwertKey': candidate.analyte.key,
        'laborwertName': candidate.analyte.display_name,
        'confidence': candidate.confidence,
        'feld': 'wert',
        'originalText': candidate.original_text,
        'erkannterWert': candidate.raw_value,
        'vorschlag': f'{decimal_to_number(candidate.corrected_value)} {candidate.corrected_unit.code}',
        'grund': ', '.join(candidate.parser_hints) if candidate.parser_hints else 'Niedrige Confidence oder unklare Zuordnung.',
    }


def latest_report(patient_id: str | None = None) -> LabReport | None:
    """Lädt den neuesten nicht-leeren Befund mit allen relevanten Relationen."""
    queryset = LabReport.objects.select_related('patient').prefetch_related('values__analyte__group', 'values__analyte__knowledge_entry', 'values__unit', 'values__reference_range').filter(values__isnull=False).distinct()
    if patient_id:
        queryset = queryset.filter(patient__public_id=patient_id)
    return queryset.order_by('-report_date', '-created_at').first()


def average_confidence(values: list[LabValue]) -> int:
    """Berechnet eine gerundete Durchschnittsconfidence."""
    if not values:
        return 0
    return round(mean(value.confidence for value in values))


def build_evaluation_view(report: LabReport | None = None) -> dict:
    """Baut die Auswertungsansicht aus normalisierten Laborwerten."""
    report = report or latest_report()
    if not report:
        return {'aktuellerBefund': '', 'vergleichsBefund': '', 'hatVergleich': False, 'zeitraum': '0 Monate', 'werte': [], 'gruppen': []}
    values = list(report.values.select_related('analyte__group', 'analyte__knowledge_entry', 'unit', 'reference_range'))
    previous = LabReport.objects.filter(patient=report.patient, report_date__lt=report.report_date, values__isnull=False).distinct().order_by('-report_date', '-created_at').first()
    return {
        'aktuellerBefund': format_date(report.report_date),
        'vergleichsBefund': format_date(previous.report_date) if previous else '',
        'hatVergleich': previous is not None,
        'zeitraum': '12 Monate' if previous else 'kein Vergleich',
        'werte': [lab_value_to_evaluation(value) for value in values],
        'gruppen': group_summary(values, detailed=True),
    }
