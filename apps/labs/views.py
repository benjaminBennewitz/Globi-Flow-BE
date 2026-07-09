# apps/labs/views.py

"""Views für Befundfreigabe und Auswertung."""

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.labs.models import LabReport
from apps.labs.presenters import build_evaluation_view, latest_report
from apps.reports.services import ensure_patient_report, has_open_review_items


def selected_report(report_id: str | None = None, patient_id: str | None = None) -> LabReport | None:
    """Lädt den gewünschten sichtbaren Befund oder den neuesten Befund mit Laborwerten."""
    if report_id:
        queryset = LabReport.objects.annotate(value_count=Count('values', distinct=True), review_count=Count('review_candidates', distinct=True)).filter(public_id=report_id).filter(Q(value_count__gt=0) | Q(review_count__gt=0))
        if patient_id:
            queryset = queryset.filter(patient__public_id=patient_id)
        report = queryset.first()
        if report:
            return report
    return latest_report(patient_id)


class EvaluationView(APIView):
    """Liefert die fachliche Auswertungsansicht."""

    def get(self, request):
        """Gibt die aktuellen Auswertungsdaten für aktiven Befund oder Patienten zurück."""
        report = selected_report(request.query_params.get('reportId') or request.query_params.get('befundId'), request.query_params.get('patientId'))
        return Response(build_evaluation_view(report))


class LabReportReleaseView(APIView):
    """Gibt einen Befund für Bericht und Verlauf frei."""

    def post(self, request, public_id: str | None = None):
        """Setzt den Befundstatus auf freigegeben."""
        report_id = public_id or request.data.get('reportId') or request.data.get('befundId')
        report = get_object_or_404(LabReport.objects.select_related('patient').filter(values__isnull=False).distinct(), public_id=report_id)
        if has_open_review_items(report):
            return Response({'detail': 'Der Befund enthält noch offene Reviewwerte.'}, status=status.HTTP_400_BAD_REQUEST)
        report.status = LabReport.Status.RELEASED
        report.released_at = timezone.now()
        report.save(update_fields=['status', 'released_at', 'updated_at'])
        patient_report = ensure_patient_report(report, release=True)
        return Response({'id': report.public_id, 'status': report.status, 'releasedAt': report.released_at.isoformat(), 'patientReportId': patient_report.public_id})
