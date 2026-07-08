# apps/dashboard/views.py

"""Aggregierte Dashboard-Views."""

from rest_framework.response import Response
from rest_framework.views import APIView
from apps.dashboard.services import build_dashboard_view, build_overview_view
from apps.labs.presenters import build_evaluation_view


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
        """Gibt die Auswertung zurück."""
        return Response(build_evaluation_view())
