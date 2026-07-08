# apps/labs/views.py

"""Views für Befundfreigabe und Auswertung."""

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.labs.models import LabReport
from apps.labs.presenters import build_evaluation_view


class EvaluationView(APIView):
    """Liefert die fachliche Auswertungsansicht."""

    def get(self, request):
        """Gibt die aktuellen Auswertungsdaten zurück."""
        return Response(build_evaluation_view())


class LabReportReleaseView(APIView):
    """Gibt einen Befund für Bericht und Verlauf frei."""

    def post(self, request, public_id: str | None = None):
        """Setzt den Befundstatus auf freigegeben."""
        report_id = public_id or request.data.get('reportId') or request.data.get('befundId')
        report = LabReport.objects.get(public_id=report_id)
        report.status = LabReport.Status.RELEASED
        report.released_at = timezone.now()
        report.save(update_fields=['status', 'released_at', 'updated_at'])
        return Response({'id': report.public_id, 'status': report.status, 'releasedAt': report.released_at.isoformat()})
