# apps/reports/views.py

"""API-Views für Patientenberichte."""

from django.db.models import Count, Q
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.labs.models import LabReport
from apps.reports.models import PatientReport
from apps.reports.presenters import build_patient_report_preview, build_print_report
from apps.reports.services import ensure_patient_report


def latest_visible_report_for_patient(patient_id: str) -> LabReport | None:
    """Lädt den neuesten nicht-leeren Befund eines Patienten."""
    return LabReport.objects.annotate(value_count=Count('values', distinct=True), review_count=Count('review_candidates', distinct=True)).filter(patient__public_id=patient_id).filter(Q(value_count__gt=0) | Q(review_count__gt=0)).order_by('-report_date', '-created_at').first()


def report_from_request(request) -> PatientReport | None:
    """Lädt oder erzeugt den Bericht passend zu Query-Parametern."""
    report_id = request.query_params.get('reportId') or request.query_params.get('befundId')
    patient_id = request.query_params.get('patientId')
    if report_id:
        lab_report = LabReport.objects.select_related('patient').filter(public_id=report_id).first()
        if lab_report:
            if patient_id and lab_report.patient.public_id != patient_id:
                fallback_report = latest_visible_report_for_patient(patient_id)
                return ensure_patient_report(fallback_report) if fallback_report else None
            return ensure_patient_report(lab_report)
        patient_report = PatientReport.objects.select_related('patient', 'lab_report').filter(public_id=report_id).first()
        if patient_report:
            if patient_id and patient_report.patient.public_id != patient_id:
                fallback_report = latest_visible_report_for_patient(patient_id)
                return ensure_patient_report(fallback_report) if fallback_report else None
            return patient_report
    if patient_id:
        lab_report = latest_visible_report_for_patient(patient_id)
        if lab_report:
            return ensure_patient_report(lab_report)
    return PatientReport.objects.select_related('patient', 'lab_report').order_by('-report_date', '-created_at').first()


class ReportPreviewView(APIView):
    """Liefert die druckfertige DIN-A4-Berichtsvorschau."""

    def get(self, request):
        """Gibt den passenden Bericht zurück."""
        return Response(build_print_report(report_from_request(request)))


class PatientReportPreviewView(APIView):
    """Liefert die kompakte Patientenbericht-Vorschau."""

    def get(self, request):
        """Gibt eine patiententaugliche Kurzansicht zurück."""
        return Response(build_patient_report_preview(report_from_request(request)))
