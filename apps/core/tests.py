# apps/core/tests.py

"""Integrations- und API-Tests für zentrale Backendfunktionen."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.urls import reverse


class HealthTests(SimpleTestCase):
    """Prüft den Health-Endpunkt ohne echte Datenbankverbindung."""

    @patch("apps.core.views.connection")
    def test_health_endpoint(self, connection_mock: MagicMock) -> None:
        """Prüft Status, Antwort und ausgeführten Datenbank-Healthcheck."""
        cursor_mock = MagicMock()
        connection_mock.cursor.return_value.__enter__.return_value = cursor_mock

        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        cursor_mock.execute.assert_called_once_with("SELECT 1")
