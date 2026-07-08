# apps/core/tests.py

"""Minimale API-Tests für den Healthcheck."""

from django.test import TestCase
from django.urls import reverse


class HealthTests(TestCase):
    """Prüft den Health-Endpunkt."""

    def test_health_endpoint(self):
        """Der Healthcheck liefert den Status ok."""
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
