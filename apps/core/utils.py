# apps/core/utils.py

"""Formatierungs- und Hilfsfunktionen für API-Präsentationen."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def decimal_to_number(value: Decimal | None) -> float | None:
    """Wandelt Decimal-Werte in JSON-freundliche Zahlen um."""
    if value is None:
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def format_date(value: date | None) -> str:
    """Formatiert ein Datum für die vorhandene Angular-Oberfläche."""
    if value is None:
        return ''
    return value.strftime('%d.%m.%Y')


def format_datetime(value: datetime | None) -> str:
    """Formatiert einen Zeitpunkt knapp für Statuslisten."""
    if value is None:
        return ''
    return value.strftime('%d.%m.%Y · %H:%M')


def public_id(prefix: str, number: int) -> str:
    """Erzeugt eine lesbare öffentliche ID."""
    return f'{prefix}-{number:06d}'


def clean_text(value: Any, fallback: str = '') -> str:
    """Normalisiert Freitext ohne HTML-Interpretation."""
    if value is None:
        return fallback
    return str(value).replace('<', '').replace('>', '').strip() or fallback
