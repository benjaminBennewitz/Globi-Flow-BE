# apps/dashboard/services.py

"""Aggregierte API-Services für Dashboard und Übersicht."""

from django.db.models import Avg, Count, Q
from apps.dashboard.models import DashboardActivity, DashboardHealthMonth, DashboardNotice
from apps.imports.models import ImportJob
from apps.imports.presenters import import_job_to_frontend
from apps.knowledge.models import KnowledgeEntry
from apps.knowledge.presenters import knowledge_to_frontend
from apps.labs.models import LabReport, LabValue, ReviewCandidate
from apps.labs.presenters import average_confidence, group_summary, lab_value_to_dashboard, review_entry_to_frontend, trend_series
from apps.patients.models import Patient
from apps.patients.serializers import PatientFrontendSerializer
from apps.reports.models import PatientReport
from apps.reports.presenters import build_patient_report_preview


def latest_values() -> list[LabValue]:
    """Lädt die Werte aus dem neuesten Befund."""
    report = LabReport.objects.prefetch_related('values__analyte__group', 'values__unit', 'values__reference_range').order_by('-report_date').first()
    if not report:
        return []
    return list(report.values.select_related('analyte__group', 'unit', 'reference_range'))


def build_dashboard_view() -> dict:
    """Baut die komplette Startansicht für das bestehende Frontend."""
    values = latest_values()
    review_candidates = ReviewCandidate.objects.select_related('report__patient', 'analyte__group', 'corrected_unit', 'reference_range').filter(status='offen')[:10]
    knowledge_entries = KnowledgeEntry.objects.select_related('analyte__group').prefetch_related('sources', 'versions')[:50]
    import_jobs = ImportJob.objects.select_related('patient').prefetch_related('steps', 'datasets', 'logs')[:10]
    return {
        'kennzahlen': {
            'befunde': LabReport.objects.count(),
            'laborwerte': LabValue.objects.count(),
            'review': ReviewCandidate.objects.filter(status='offen').count(),
            'berichte': PatientReport.objects.filter(status='freigegeben').count(),
            'confidence': average_confidence(values),
        },
        'importjobs': [import_job_to_frontend(job) for job in import_jobs],
        'laborwerte': [lab_value_to_dashboard(value) for value in values],
        'gruppen': group_summary(values),
        'trends': trend_series(values),
        'reviewEintraege': [review_entry_to_frontend(candidate) for candidate in review_candidates],
        'wissenseintraege': [knowledge_to_frontend(entry) for entry in knowledge_entries],
        'patientenbericht': build_patient_report_preview(),
    }


def build_overview_view() -> dict:
    """Baut die aggregierte Praxisübersicht."""
    imports_checked = ImportJob.objects.filter(status__in=['review', 'abgeschlossen']).count()
    imports_open = ImportJob.objects.exclude(status__in=['review', 'abgeschlossen']).count()
    return {
        'kennzahlen': {
            'patientenGesamt': Patient.objects.count(),
            'berichteGesamt': LabReport.objects.count(),
            'importeGeprueft': imports_checked,
            'importeUngeprueft': imports_open,
            'berichteFreigegeben': PatientReport.objects.filter(status='freigegeben').count(),
            'reviewOffen': ReviewCandidate.objects.filter(status='offen').count(),
        },
        'gesundheitsverlauf': [
            {'jahr': item.year, 'monat': item.month, 'label': item.label, 'unauffaellig': item.normal_count, 'auffaellig': item.abnormal_count}
            for item in DashboardHealthMonth.objects.all()
        ],
        'dringendeHinweise': [
            {'id': item.public_id, 'titel': item.title, 'beschreibung': item.description, 'seit': item.since, 'status': item.status}
            for item in DashboardNotice.objects.all()
        ],
        'aktivitaeten': [
            {'id': item.public_id, 'zeitpunkt': item.time_label, 'tagOffset': item.day_offset, 'titel': item.title, 'beschreibung': item.description, 'status': item.status}
            for item in DashboardActivity.objects.all()[:30]
        ],
    }


def build_patient_list() -> list[dict]:
    """Gibt Patienten im Frontendformat aus."""
    queryset = Patient.objects.prefetch_related('lab_reports__values', 'lab_reports__review_candidates', 'patient_reports')
    return PatientFrontendSerializer(queryset, many=True).data
