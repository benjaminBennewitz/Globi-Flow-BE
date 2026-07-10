# apps/core/input_validation.py

"""Zentrale Validierung und Normalisierung nicht vertrauenswürdiger API-Eingaben."""

import re
import unicodedata
from rest_framework.exceptions import ValidationError

CONTROL_PATTERN = re.compile(r'[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]')
DANGEROUS_PATTERN = re.compile(r'(?:javascript|vbscript|data)\s*:|on(?:error|load|click|mouseover)\s*=|<\/?\s*script\b', re.IGNORECASE)
HTML_PATTERN = re.compile(r'[<>`]')
KEY_PATTERN = re.compile(r'^[\w.-]+$', re.UNICODE)
NAME_PATTERN = re.compile(r"^[\w\s.\-']+$", re.UNICODE)

def clean_text(value, *, field: str, max_length: int, multiline: bool = True, allow_blank: bool = True) -> str:
    """Normalisiert Text und blockiert aktive Inhalte sowie unsichtbare Steuerzeichen."""
    text = unicodedata.normalize('NFKC', str(value or ''))
    text = CONTROL_PATTERN.sub('\n' if multiline else '', text)
    if DANGEROUS_PATTERN.search(text) or HTML_PATTERN.search(text):
        raise ValidationError({field: 'Aktive Inhalte, HTML und Script-Fragmente sind nicht erlaubt.'})
    text = re.sub(r'[ \t]+', ' ', text).strip()
    if not allow_blank and not text:
        raise ValidationError({field: 'Dieses Feld darf nicht leer sein.'})
    if len(text) > max_length:
        raise ValidationError({field: f'Maximal {max_length} Zeichen sind erlaubt.'})
    return text

def clean_key(value, *, field: str = 'laborwertKey', max_length: int = 100) -> str:
    """Validiert technische Schlüssel über eine enge Positivliste."""
    text = clean_text(value, field=field, max_length=max_length, multiline=False, allow_blank=False)
    if not KEY_PATTERN.fullmatch(text):
        raise ValidationError({field: 'Erlaubt sind nur Buchstaben, Zahlen, Punkt, Unterstrich und Bindestrich.'})
    return text

def clean_name(value, *, field: str, max_length: int = 100, allow_blank: bool = True) -> str:
    """Validiert Namen und kurze Bezeichnungen über eine Positivliste."""
    text = clean_text(value, field=field, max_length=max_length, multiline=False, allow_blank=allow_blank)
    if text and not NAME_PATTERN.fullmatch(text):
        raise ValidationError({field: 'Die Bezeichnung enthält nicht erlaubte Zeichen.'})
    return text
