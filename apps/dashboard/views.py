# apps/dashboard/views.py

"""Aggregierte Dashboard-Views."""

from django.db.models import Count, Q
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.dashboard.services import build_dashboard_view, build_overview_view
from apps.labs.models import LabReport
from apps.labs.presenters import build_evaluation_view, latest_report


def selected_report(report_id: str | None = None, patient_id: str | None = None) -> LabReport | None:
    """Lädt den gewünschten Befund oder den neuesten Befund der Testperson."""
    if report_id:
        queryset = LabReport.objects.annotate(value_count=Count('values', distinct=True), review_count=Count('review_candidates', distinct=True)).filter(public_id=report_id).filter(Q(value_count__gt=0) | Q(review_count__gt=0))
        if patient_id:
            queryset = queryset.filter(patient__public_id=patient_id)
        report = queryset.select_related('patient').first()
        if report:
            return report

    return latest_report(patient_id)


class DashboardView(APIView):
    """Liefert die kombinierte Dashboard-Startansicht."""

    def get(self, request):
        """Gibt alle Startansichtsdaten zurück."""
        return Response(build_dashboard_view())


class OverviewView(APIView):
    """Liefert die aggregierte Übersichtsroute."""

    def get(self, request):
        """Gibt Praxiskennzahlen und Aktivitätsdaten zurück."""
        return Response(build_overview_view())


class EvaluationAliasView(APIView):
    """Alias für die vorhandene Auswertungsroute."""

    def get(self, request):
        """Gibt die Auswertung für aktiven Patient und aktiven Befund zurück."""
        report = selected_report(request.query_params.get('reportId') or request.query_params.get('befundId'), request.query_params.get('patientId'))
        return Response(build_evaluation_view(report))
