# apps/imports/parser.py

"""Einfacher lokaler Laborwert-Parser für optimierte Testdaten-PDFs."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from apps.labs.models import LabAnalyte

VALUE_PATTERN = re.compile(r'(?P<value>-?\d+(?:[,.]\d+)?)\s*(?P<unit>[A-Za-zµ%./]+)?\s*(?:\(?\s*(?P<ref_low>-?\d+(?:[,.]\d+)?)?\s*[-–]\s*(?P<ref_high>-?\d+(?:[,.]\d+)?)\s*(?P<ref_unit>[A-Za-zµ%./]+)?\s*\)?)?')
REFERENCE_RANGE_PATTERN = re.compile(r'(?P<low>-?\d+(?:[,.]\d+)?)\s*[-–]\s*(?P<high>-?\d+(?:[,.]\d+)?)')
REFERENCE_LT_PATTERN = re.compile(r'^\s*<\s*(?P<high>-?\d+(?:[,.]\d+)?)')
REFERENCE_GT_PATTERN = re.compile(r'^\s*>\s*(?P<low>-?\d+(?:[,.]\d+)?)')

SPECIAL_ALIASES = {
    'ldl chol': 'ldl',
    'ldl cholesterin': 'ldl',
    'ferr': 'ferritin',
    '25 oh vit d': 'vitamin_d',
    '25 oh vitamin d': 'vitamin_d',
    'vit d': 'vitamin_d',
    'vitamin d': 'vitamin_d',
    'haemoglobin': 'haemoglobin',
    'hämoglobin': 'haemoglobin',
}

REVIEW_ALIAS_KEYS = {'ldl', 'ferritin', 'vitamin_d'}


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


def normalize_text(value: str) -> str:
    """Normalisiert Suchtexte für Aliasvergleiche."""
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', 'µ': 'u'}
    result = str(value or '').strip().lower()
    for source, target in replacements.items():
        result = result.replace(source, target)
    return ' '.join(''.join(char if char.isalnum() else ' ' for char in result).split())


def slug_key(value: str, fallback: str = 'laborwert') -> str:
    """Erzeugt einen stabilen ASCII-Key für neue Parserwerte."""
    key = normalize_text(value).replace(' ', '_')
    return key or fallback


def parser_aliases() -> list[tuple[LabAnalyte, list[str]]]:
    """Lädt Laborwert-Aliasse aus der Datenbank."""
    analytes = LabAnalyte.objects.select_related('group').filter(is_active=True)
    result = []
    for analyte in analytes:
        aliases = {analyte.display_name, analyte.key.replace('_', ' '), *[str(alias) for alias in analyte.aliases]}
        result.append((analyte, sorted({normalize_text(alias) for alias in aliases if alias}, key=len, reverse=True)))
    return result


def resolve_analyte(display_name: str, aliases: list[tuple[LabAnalyte, list[str]]]) -> tuple[str, str] | None:
    """Findet einen vorhandenen Laborwert anhand von Anzeigename oder Spezialalias."""
    normalized = normalize_text(display_name)
    special_key = SPECIAL_ALIASES.get(normalized)
    if special_key:
        for analyte, _ in aliases:
            if analyte.key == special_key:
                return analyte.key, analyte.display_name
        return special_key, display_name.strip()

    for analyte, names in aliases:
        if normalized in names:
            return analyte.key, analyte.display_name

    return None


def parse_reference(reference: str) -> tuple[Decimal, Decimal]:
    """Liest Referenzbereiche wie `13,5 - 17,5`, `< 5,0` oder `> 30`."""
    clean = str(reference or '').strip()
    range_match = REFERENCE_RANGE_PATTERN.search(clean)
    if range_match:
        return to_decimal(range_match.group('low')), to_decimal(range_match.group('high'))

    lt_match = REFERENCE_LT_PATTERN.search(clean)
    if lt_match:
        return Decimal('0'), to_decimal(lt_match.group('high'))

    gt_match = REFERENCE_GT_PATTERN.search(clean)
    if gt_match:
        return to_decimal(gt_match.group('low')), Decimal('999999')

    return Decimal('0'), Decimal('999999')


def parse_table_lines(text: str, aliases: list[tuple[LabAnalyte, list[str]]]) -> list[ParsedLabValue]:
    """Parst die optimierte Testdaten-PDF mit spaltenweise extrahierter Textschicht."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header_index = -1

    for index in range(0, max(0, len(lines) - 4)):
        if [normalize_text(item) for item in lines[index:index + 5]] == ['gruppe', 'laborwert', 'ergebnis', 'einheit', 'referenz']:
            header_index = index + 5
            break

    if header_index < 0:
        return []

    parsed: list[ParsedLabValue] = []
    index = header_index

    while index + 4 < len(lines):
        group_name = lines[index]
        display_name = lines[index + 1]
        value_text = lines[index + 2]
        unit = lines[index + 3]
        reference = lines[index + 4]

        if normalize_text(group_name).startswith('parser hinweise') or normalize_text(group_name).startswith('disclaimer'):
            break

        if not re.search(r'\d', value_text) or not re.search(r'\d', reference):
            index += 1
            continue

        resolved = resolve_analyte(display_name, aliases)
        analyte_key = resolved[0] if resolved else slug_key(display_name)
        normalized_display_name = resolved[1] if resolved else display_name.strip()
        reference_min, reference_max = parse_reference(reference)
        confidence = 96

        if analyte_key in REVIEW_ALIAS_KEYS:
            confidence = 72 if analyte_key != 'vitamin_d' else 68

        parsed.append(ParsedLabValue(analyte_key=analyte_key, display_name=normalized_display_name, group_name=group_name.strip(), value=to_decimal(value_text), unit=unit.strip(), reference_min=reference_min, reference_max=reference_max, original_text=f'{group_name} · {display_name} · {value_text} {unit} · Referenz {reference}', confidence=confidence))
        index += 5

    return parsed


def parse_inline_values(text: str, aliases: list[tuple[LabAnalyte, list[str]]]) -> list[ParsedLabValue]:
    """Fallback für einfache zeilenbasierte Laborwerttexte."""
    parsed = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line_lower = normalize_text(line)
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


def parse_lab_values(text: str) -> list[ParsedLabValue]:
    """Erkennt Laborwert-Zeilen anhand von Tabellenstruktur und gepflegten Aliassen."""
    aliases = parser_aliases()
    table_values = parse_table_lines(text, aliases)
    if table_values:
        return table_values
    return parse_inline_values(text, aliases)
