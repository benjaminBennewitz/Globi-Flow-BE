# apps/reports/presenters.py

"""Präsentationsfunktionen für Patientenberichte."""

from apps.core.utils import decimal_to_number, format_date
from apps.labs.models import LabValue, ReviewCandidate
from apps.labs.presenters import group_summary, trend_direction, value_history, previous_value
from apps.reports.models import PatientReport
from apps.reports.report_template import get_report_template
from apps.reports.services import open_review_candidates, report_counts, review_value_ids


def patient_hint(value: LabValue, knowledge) -> str:
    """Gibt einen patiententauglichen Hinweis ohne technische Importnotizen zurück."""
    hint = (value.hint or '').strip()
    technical_fragments = ['aus lokalem import erkannt', 'demo-wert', 'parser']
    if hint and not any(fragment in hint.lower() for fragment in technical_fragments):
        return hint
    return (knowledge.notes if knowledge else '') or ''


def value_to_report(value: LabValue) -> dict:
    """Gibt einen Laborwert für die Druckansicht aus."""
    knowledge = getattr(value.analyte, 'knowledge_entry', None)
    previous = previous_value(value)
    return {
        'key': value.analyte.key,
        'name': value.analyte.display_name,
        'gruppe': value.analyte.group.name,
        'wert': decimal_to_number(value.value),
        'einheit': value.unit.code,
        'referenzMin': decimal_to_number(value.reference_range.lower),
        'referenzMax': decimal_to_number(value.reference_range.upper),
        'status': value.status,
        'trend': trend_direction(value.value, previous.value if previous else None),
        'erklaerung': knowledge.patient_short_text if knowledge else '',
        'hinweis': patient_hint(value, knowledge),
        'verlauf': [decimal_to_number(entry.value) for entry in value_history(value)][-6:],
    }


def missing_knowledge_entries(values: list[LabValue]) -> list[dict]:
    """Listet Laborwerte ohne Patientenkurztext in der Wissensbasis."""
    result = []
    for value in values:
        knowledge = getattr(value.analyte, 'knowledge_entry', None)
        if knowledge and knowledge.patient_short_text:
            continue
        result.append({
            'id': value.analyte.key,
            'name': value.analyte.display_name,
            'gruppe': value.analyte.group.name,
            'hinweis': 'Patientenkurztext in der Wissensbasis fehlt.',
        })
    return result


def open_review_entries(report: PatientReport) -> list[dict]:
    """Listet offene Reviewpunkte des Berichtsbefunds für den Freigabecheck."""
    if not report.lab_report:
        return []
    entries = []
    for candidate in open_review_candidates(report.lab_report):
        entries.append({
            'id': candidate.public_id,
            'name': candidate.analyte.display_name,
            'gruppe': candidate.analyte.group.name,
            'hinweis': candidate.comment or 'Dieser OCR-/Importwert muss noch geprüft werden.',
        })
    review_candidate_value_ids = {candidate.lab_value_id for candidate in open_review_candidates(report.lab_report) if candidate.lab_value_id}
    values = report.lab_report.values.select_related('analyte__group').filter(review_status=LabValue.ReviewStatus.REVIEW)
    for value in values:
        if value.id in review_candidate_value_ids:
            continue
        entries.append({
            'id': value.public_id,
            'name': value.analyte.display_name,
            'gruppe': value.analyte.group.name,
            'hinweis': 'Dieser Laborwert ist noch nicht freigegeben.',
        })
    return entries


def build_print_report(report: PatientReport | None = None) -> dict:
    """Baut die druckfertige Berichtsvorschau."""
    report = report or PatientReport.objects.select_related('patient', 'lab_report').prefetch_related('sections', 'questions', 'recommendations', 'sources').order_by('-report_date').first()
    if report is None:
        return {'template': get_report_template(), 'id': '', 'berichtsdatum': '', 'version': '1.0', 'gesamtstatus': '', 'gesamttext': '', 'gesamtWerte': 0, 'gepruefteWerte': 0, 'normaleWerte': 0, 'auffaelligeWerte': 0, 'reviewWerte': 0, 'werte': [], 'kategorien': [], 'empfehlungen': [], 'fragen': [], 'quellen': [], 'disclaimer': '', 'istDruckbar': False, 'wissensbasisVollstaendig': True, 'fehlendeWissensbasisTexte': [], 'offeneReviewEintraege': []}
    values = list(report.lab_report.values.select_related('analyte__group', 'unit', 'reference_range', 'analyte__knowledge_entry')) if report.lab_report else []
    counts = report_counts(report.lab_report) if report.lab_report else {'total': 0, 'checked': 0, 'normal': 0, 'abnormal': 0, 'review': 0}
    review_ids = review_value_ids(report.lab_report) if report.lab_report else set()
    visible_values = [value for value in values if value.id not in review_ids]
    missing_entries = missing_knowledge_entries(visible_values)
    review_entries = open_review_entries(report)
    return {
        'template': get_report_template(),
        'id': report.public_id,
        'berichtsdatum': format_date(report.report_date),
        'version': report.version,
        'gesamtstatus': report.total_status,
        'gesamttext': report.total_text,
        'gesamtWerte': counts['total'],
        'gepruefteWerte': counts['checked'],
        'normaleWerte': counts['normal'],
        'auffaelligeWerte': counts['abnormal'],
        'reviewWerte': counts['review'],
        'werte': [value_to_report(value) for value in visible_values],
        'kategorien': [{'name': item['name'], 'normal': item['normal'], 'auffaellig': item['auffaellig'], 'review': item['review']} for item in group_summary(visible_values)],
        'empfehlungen': [{'id': item.public_id, 'titel': item.title, 'text': item.text, 'prioritaet': item.priority} for item in report.recommendations.all()],
        'fragen': [item.question for item in report.questions.all()],
        'quellen': [{'id': item.public_id, 'bereich': item.area, 'titel': item.title, 'stand': item.source_date} for item in report.sources.all()],
        'disclaimer': report.disclaimer,
        'istDruckbar': counts['review'] == 0,
        'wissensbasisVollstaendig': len(missing_entries) == 0,
        'fehlendeWissensbasisTexte': missing_entries,
        'offeneReviewEintraege': review_entries,
    }


def build_patient_report_preview(report: PatientReport | None = None) -> dict:
    """Baut die kompakte Patientenbericht-Vorschau für die Startansicht."""
    report = report or PatientReport.objects.prefetch_related('sections', 'questions').order_by('-report_date').first()
    if report is None:
        return {'id': '', 'testperson': '', 'berichtsdatum': '', 'zusammenfassung': '', 'abschnitte': [], 'fragen': [], 'disclaimer': ''}
    return {
        'template': get_report_template(),
        'id': report.public_id,
        'testperson': report.patient.display_name,
        'berichtsdatum': format_date(report.report_date),
        'zusammenfassung': report.summary or report.total_text,
        'abschnitte': [{'key': section.key, 'titel': section.title, 'text': section.text} for section in report.sections.all()],
        'fragen': [{'id': question.public_id, 'frage': question.question, 'bereich': question.area} for question in report.questions.all()],
        'disclaimer': report.disclaimer,
    }
