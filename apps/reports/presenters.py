# apps/reports/presenters.py

"""Präsentationsfunktionen für Patientenberichte."""

from apps.core.utils import decimal_to_number, format_date
from apps.labs.models import LabValue
from apps.labs.presenters import group_summary, trend_direction, value_history, previous_value
from apps.reports.models import PatientReport


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
        'hinweis': value.hint or (knowledge.notes if knowledge else ''),
        'verlauf': [decimal_to_number(entry.value) for entry in value_history(value)][-6:],
    }


def build_print_report(report: PatientReport | None = None) -> dict:
    """Baut die druckfertige Berichtsvorschau."""
    report = report or PatientReport.objects.select_related('patient', 'lab_report').prefetch_related('sections', 'questions', 'recommendations', 'sources').order_by('-report_date').first()
    if report is None:
        return {'id': '', 'berichtsdatum': '', 'version': '1.0', 'gesamtstatus': '', 'gesamttext': '', 'gepruefteWerte': 0, 'normaleWerte': 0, 'auffaelligeWerte': 0, 'reviewWerte': 0, 'werte': [], 'kategorien': [], 'empfehlungen': [], 'fragen': [], 'quellen': [], 'disclaimer': ''}
    values = list(report.lab_report.values.select_related('analyte__group', 'unit', 'reference_range', 'analyte__knowledge_entry')) if report.lab_report else []
    return {
        'id': report.public_id,
        'berichtsdatum': format_date(report.report_date),
        'version': report.version,
        'gesamtstatus': report.total_status,
        'gesamttext': report.total_text,
        'gepruefteWerte': report.checked_values,
        'normaleWerte': report.normal_values,
        'auffaelligeWerte': report.abnormal_values,
        'reviewWerte': report.review_values,
        'werte': [value_to_report(value) for value in values],
        'kategorien': [{'name': item['name'], 'normal': item['normal'], 'auffaellig': item['auffaellig'], 'review': item['review']} for item in group_summary(values)],
        'empfehlungen': [{'id': item.public_id, 'titel': item.title, 'text': item.text, 'prioritaet': item.priority} for item in report.recommendations.all()],
        'fragen': [item.question for item in report.questions.all()],
        'quellen': [{'id': item.public_id, 'bereich': item.area, 'titel': item.title, 'stand': item.source_date} for item in report.sources.all()],
        'disclaimer': report.disclaimer,
    }


def build_patient_report_preview(report: PatientReport | None = None) -> dict:
    """Baut die kompakte Patientenbericht-Vorschau für die Startansicht."""
    report = report or PatientReport.objects.prefetch_related('sections', 'questions').order_by('-report_date').first()
    if report is None:
        return {'id': '', 'testperson': '', 'berichtsdatum': '', 'zusammenfassung': '', 'abschnitte': [], 'fragen': [], 'disclaimer': ''}
    return {
        'id': report.public_id,
        'testperson': report.patient.display_name,
        'berichtsdatum': format_date(report.report_date),
        'zusammenfassung': report.summary or report.total_text,
        'abschnitte': [{'key': section.key, 'titel': section.title, 'text': section.text} for section in report.sections.all()],
        'fragen': [{'id': question.public_id, 'frage': question.question, 'bereich': question.area} for question in report.questions.all()],
        'disclaimer': report.disclaimer,
    }
