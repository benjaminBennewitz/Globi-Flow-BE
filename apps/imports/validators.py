# apps/imports/validators.py

"""Validierung lokaler Upload-Dateien."""

from pathlib import PurePath
from django.conf import settings
from rest_framework.exceptions import ValidationError
from apps.imports.malware_scanner import scan_pdf_upload


def validate_pdf_upload(uploaded_file) -> None:
    """Prüft Dateigröße, Endung und PDF-Signatur."""
    if uploaded_file.size <= 0:
        raise ValidationError('Die Datei ist leer.')

    if uploaded_file.size > settings.GLOBI_MAX_UPLOAD_BYTES:
        raise ValidationError(f'Die Datei ist zu groß. Erlaubt sind maximal {settings.GLOBI_MAX_UPLOAD_MB} MB.')

    filename = PurePath(str(uploaded_file.name)).name
    if filename != uploaded_file.name or '..' in filename or len(filename) > 120:
        raise ValidationError('Der Dateiname ist ungültig.')

    if not filename.lower().endswith('.pdf'):
        raise ValidationError('Es sind nur PDF-Dateien erlaubt.')

    content_type = str(getattr(uploaded_file, 'content_type', '') or '').lower()
    if content_type and content_type != 'application/pdf':
        raise ValidationError('Der gemeldete Dateityp ist keine PDF-Datei.')

    position = uploaded_file.tell()
    signature = uploaded_file.read(5)
    uploaded_file.seek(position)

    if signature != b'%PDF-':
        raise ValidationError('Die Datei besitzt keine gültige PDF-Signatur.')

    scan_pdf_upload(uploaded_file)
