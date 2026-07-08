# apps/core/views.py

"""Allgemeine API-Views."""

from django.db import connection
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Prüft API- und Datenbankverfügbarkeit."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """Liefert einen einfachen Healthcheck."""
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()

        return Response({'status': 'ok', 'database': 'ok', 'service': 'Globi-Flow-BE'})
