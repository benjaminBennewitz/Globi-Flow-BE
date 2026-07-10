# apps/imports/tests_security.py

"""Security-Tests für lokale PDF-Uploads."""

from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from pypdf import PdfWriter
from rest_framework.exceptions import ValidationError

from apps.imports.validators import validate_pdf_upload


class PdfUploadSecurityTests(SimpleTestCase):
    """Prüft Signatur, aktive Inhalte und Scanner-Ausfälle."""

    def valid_pdf(self) -> bytes:
        """Erzeugt eine minimale valide Test-PDF."""
        buffer = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(buffer)
        return buffer.getvalue()

    def test_valid_pdf_is_accepted(self):
        """Akzeptiert eine strukturell valide PDF ohne aktive Inhalte."""
        upload = SimpleUploadedFile("labor.pdf", self.valid_pdf(), content_type="application/pdf")
        validate_pdf_upload(upload)

    def test_javascript_pdf_is_rejected(self):
        """Blockiert JavaScript-Marker in einer PDF."""
        upload = SimpleUploadedFile("labor.pdf", self.valid_pdf() + b"/JavaScript", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_pdf_upload(upload)

    @override_settings(GLOBI_CLAMAV_ENABLED=True, GLOBI_CLAMAV_REQUIRED=True)
    @patch("apps.imports.malware_scanner.socket.create_connection", side_effect=OSError)
    def test_required_clamav_must_be_reachable(self, _connection):
        """Lehnt Uploads ab, wenn ein verpflichtender Scanner nicht erreichbar ist."""
        upload = SimpleUploadedFile("labor.pdf", self.valid_pdf(), content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_pdf_upload(upload)
