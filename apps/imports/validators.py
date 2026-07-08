# apps/imports/validators.py

"""Validierung lokaler Upload-Dateien."""

from django.conf import settings
from rest_framework.exceptions import ValidationError


def validate_pdf_upload(uploaded_file) -> None:
    """Prüft Dateigröße, Endung und PDF-Signatur."""
    if uploaded_file.size > settings.GLOBI_MAX_UPLOAD_BYTES:
        raise ValidationError(f'Die Datei ist zu groß. Erlaubt sind maximal {settings.GLOBI_MAX_UPLOAD_MB} MB.')

    if not uploaded_file.name.lower().endswith('.pdf'):
        raise ValidationError('Es sind nur PDF-Dateien erlaubt.')

    position = uploaded_file.tell()
    signature = uploaded_file.read(5)
    uploaded_file.seek(position)

    if signature != b'%PDF-':
        raise ValidationError('Die Datei besitzt keine gültige PDF-Signatur.')
