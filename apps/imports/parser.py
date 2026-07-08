# apps/imports/parser.py

"""Einfacher lokaler Laborwert-Parser für optimierte Testdaten-PDFs."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from apps.labs.models import LabAnalyte

VALUE_PATTERN = re.compile(r'(?P<value>-?\d+(?:[,.]\d+)?)\s*(?P<unit>[A-Za-zµ%./]+)?\s*(?:\(?\s*(?P<ref_low>-?\d+(?:[,.]\d+)?)?\s*[-–]\s*(?P<ref_high>-?\d+(?:[,.]\d+)?)\s*(?P<ref_unit>[A-Za-zµ%./]+)?\s*\)?)?')


@dataclass(frozen=True)
class ParsedLabValue:
    """Normalisierter Parser-Kandidat."""

    analyte_key: str
    display_name: str
    group_name: str
    value: Decimal
    unit: str
    reference_min: Decimal
    reference_max: Decimal
    original_text: str
    confidence: int


def to_decimal(value: str | None, fallback: Decimal = Decimal('0')) -> Decimal:
    """Wandelt Parserwerte robust in Decimal um."""
    if not value:
        return fallback
    try:
        return Decimal(value.replace(',', '.'))
    except InvalidOperation:
        return fallback


def parser_aliases() -> list[tuple[LabAnalyte, list[str]]]:
    """Lädt Laborwert-Aliasse aus der Datenbank."""
    analytes = LabAnalyte.objects.select_related('group').filter(is_active=True)
    result = []
    for analyte in analytes:
        aliases = {analyte.display_name.lower(), analyte.key.replace('_', ' ').lower(), *[str(alias).lower() for alias in analyte.aliases]}
        result.append((analyte, sorted(aliases, key=len, reverse=True)))
    return result


def parse_lab_values(text: str) -> list[ParsedLabValue]:
    """Erkennt einfache Laborwert-Zeilen anhand gepflegter Laborwert-Aliasse."""
    parsed = []
    aliases = parser_aliases()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line_lower = line.lower()
        for analyte, names in aliases:
            matched_alias = next((alias for alias in names if alias and alias in line_lower), '')
            if not matched_alias:
                continue
            remaining = line_lower.replace(matched_alias, ' ', 1)
            match = VALUE_PATTERN.search(remaining)
            if not match:
                continue
            unit = match.group('unit') or match.group('ref_unit') or ''
            reference_min = to_decimal(match.group('ref_low'))
            reference_max = to_decimal(match.group('ref_high'), Decimal('999999'))
            confidence = 92 if reference_max != Decimal('999999') and unit else 72
            parsed.append(ParsedLabValue(analyte.key, analyte.display_name, analyte.group.name, to_decimal(match.group('value')), unit, reference_min, reference_max, line, confidence))
            break
    return parsed
