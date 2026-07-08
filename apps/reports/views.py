# apps/reports/views.py

"""API-Views für Patientenberichte."""

from rest_framework.response import Response
from rest_framework.views import APIView
from apps.reports.presenters import build_patient_report_preview, build_print_report


class ReportPreviewView(APIView):
    """Liefert die druckfertige DIN-A4-Berichtsvorschau."""

    def get(self, request):
        """Gibt den neuesten Bericht zurück."""
        return Response(build_print_report())


class PatientReportPreviewView(APIView):
    """Liefert die kompakte Patientenbericht-Vorschau."""

    def get(self, request):
        """Gibt eine patiententaugliche Kurzansicht zurück."""
        return Response(build_patient_report_preview())
