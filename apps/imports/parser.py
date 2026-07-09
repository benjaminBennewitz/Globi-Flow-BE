# apps/imports/parser.py

"""Lokaler Laborwert-Parser für Textschicht- und OCR-Befunde."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from apps.labs.models import LabAnalyte

VALUE_PATTERN = re.compile(r'(?P<value>-?\d+(?:[,.]\d+)?)\s*(?P<unit>[A-Za-zµ%./0-9]+)?\s*(?:\(?\s*(?P<ref_low>-?\d+(?:[,.]\d+)?)?\s*[-–]\s*(?P<ref_high>-?\d+(?:[,.]\d+)?)\s*(?P<ref_unit>[A-Za-zµ%./0-9]+)?\s*\)?)?')
REFERENCE_RANGE_PATTERN = re.compile(r'(?P<low>-?\d+(?:[,.]\d+)?)\s*[-–]\s*(?P<high>-?\d+(?:[,.]\d+)?)')
REFERENCE_LT_PATTERN = re.compile(r'^\s*(?:<|≤|<=)\s*(?P<high>-?\d+(?:[,.]\d+)?)')
REFERENCE_GT_PATTERN = re.compile(r'^\s*(?:>|≥|>=)\s*(?P<low>-?\d+(?:[,.]\d+)?)')
OCR_ROW_PATTERN = re.compile(r'^(?P<name>[A-Za-zÄÖÜäöüßγΓµ/().\- 0-9]+?)\s+(?P<flag>[+-])?\s*(?P<value>-?\d+(?:[,.]\d+)?)\s+(?P<unit>[A-Za-zµ%/.0-9]+(?:/[A-Za-z0-9.]+)?)\s*(?P<reference>(?:(?:[<>]=?|≥|≤)\s*)?-?\d+(?:[,.]\d+)?(?:\s*[-–]\s*-?\d+(?:[,.]\d+)?)?)?\s*$', re.IGNORECASE)

SPECIAL_ALIASES = {
    'ldl chol': 'ldl_cholesterin',
    'ldl cholesterin': 'ldl_cholesterin',
    'ferr': 'ferritin',
    '25 oh vit d': 'vitamin_d',
    '25 oh vitamin d': 'vitamin_d',
    'vit d': 'vitamin_d',
    'vitamin d': 'vitamin_d',
    'haemoglobin': 'haemoglobin',
    'hämoglobin': 'haemoglobin',
}

REVIEW_ALIAS_KEYS = {'ldl', 'ldl_cholesterin', 'ferritin', 'vitamin_d'}
SKIP_LINE_FRAGMENTS = {
    'dachverband',
    'mailboxbefund',
    'patient',
    'geburtsdatum',
    'postfach',
    'telefon',
    'telefax',
    'murriger',
    'tomphecke',
    'kasse',
    'endbefund',
    'eingangsdatum',
    'untersuchung',
    'referenzbereich',
    'zielwerte',
    'guidelines',
    'risiko:',
}

KNOWN_ANALYTE_PROFILES = [
    {'key': 'leukozyten', 'display': 'Leukozyten', 'group': 'Blutbild', 'aliases': ['leukozyten']},
    {'key': 'erythrozyten', 'display': 'Erythrozyten', 'group': 'Blutbild', 'aliases': ['erythrozyten', 'brythrozyten']},
    {'key': 'haemoglobin', 'display': 'Hämoglobin', 'group': 'Blutbild', 'aliases': ['hämoglobin', 'haemoglobin', 'hamoglobin']},
    {'key': 'haematokrit', 'display': 'Hämatokrit', 'group': 'Blutbild', 'aliases': ['hämatokrit', 'haematokrit', 'hamatokrit']},
    {'key': 'mcv', 'display': 'MCV', 'group': 'Blutbild', 'aliases': ['mcv']},
    {'key': 'mch', 'display': 'MCH', 'group': 'Blutbild', 'aliases': ['mch']},
    {'key': 'mchc', 'display': 'MCHC', 'group': 'Blutbild', 'aliases': ['mchc']},
    {'key': 'thrombozyten', 'display': 'Thrombozyten', 'group': 'Blutbild', 'aliases': ['thrombozyten']},
    {'key': 'natrium', 'display': 'Natrium', 'group': 'Mineralhaushalt', 'aliases': ['natrium']},
    {'key': 'kalium', 'display': 'Kalium', 'group': 'Mineralhaushalt', 'aliases': ['kalium']},
    {'key': 'calcium', 'display': 'Calcium', 'group': 'Mineralhaushalt', 'aliases': ['calcium']},
    {'key': 'cholesterin', 'display': 'Cholesterin', 'group': 'Fettstoffwechsel', 'aliases': ['cholesterin']},
    {'key': 'hdl', 'display': 'HDL-Cholesterin', 'group': 'Fettstoffwechsel', 'aliases': ['hdl cholesterin', 'hdl cholesterol']},
    {'key': 'ldl', 'display': 'LDL-Cholesterin', 'group': 'Fettstoffwechsel', 'aliases': ['ldl cholesterin', 'ldl cholesterol']},
    {'key': 'ldl_hdl_risiko_index', 'display': 'LDL/HDL Risiko Index', 'group': 'Fettstoffwechsel', 'aliases': ['ldl hdl risiko index']},
    {'key': 'non_hdl_cholesterin', 'display': 'Non-HDL-Cholesterin', 'group': 'Fettstoffwechsel', 'aliases': ['non hdl cholesterin']},
    {'key': 'triglyzeride', 'display': 'Triglyzeride', 'group': 'Fettstoffwechsel', 'aliases': ['triglyceride', 'triglyzeride']},
    {'key': 'glukose', 'display': 'Glukose nüchtern', 'group': 'Stoffwechsel', 'aliases': ['glucose', 'glukose']},
    {'key': 'gesamteiweiss', 'display': 'Gesamteiweiß', 'group': 'Stoffwechsel', 'aliases': ['gesamteiweiss', 'gesamteiweiß']},
    {'key': 'bilirubin_gesamt', 'display': 'Bilirubin gesamt', 'group': 'Stoffwechsel', 'aliases': ['bilirubin gesamt']},
    {'key': 'harnsaeure', 'display': 'Harnsäure', 'group': 'Niere', 'aliases': ['harnsäure', 'harnsaeure', 'harnsaure']},
    {'key': 'harnstoff', 'display': 'Harnstoff', 'group': 'Niere', 'aliases': ['harnstoff']},
    {'key': 'kreatinin', 'display': 'Kreatinin', 'group': 'Niere', 'aliases': ['kreatinin', 'creatinin', 'creatinine']},
    {'key': 'egfr', 'display': 'eGFR', 'group': 'Niere', 'aliases': ['egfr', 'egfr ckd epi formel']},
    {'key': 'ast', 'display': 'AST', 'group': 'Leber', 'aliases': ['got', 'got asat', 'asat', 'ast']},
    {'key': 'alt', 'display': 'ALT', 'group': 'Leber', 'aliases': ['gpt', 'gpt alat', 'alat', 'alt']},
    {'key': 'ggt', 'display': 'GGT', 'group': 'Leber', 'aliases': ['ggt', 'g gt', 'gamma gt', 'y gt', 'γ gt']},
    {'key': 'alkalische_phosphatase', 'display': 'Alkalische Phosphatase', 'group': 'Leber', 'aliases': ['alkalische phosphatase', 'ap']},
    {'key': 'ldh', 'display': 'LDH', 'group': 'Leber', 'aliases': ['ldh']},
    {'key': 'crp', 'display': 'CRP', 'group': 'Entzündung', 'aliases': ['crp']},
    {'key': 'tsh', 'display': 'TSH', 'group': 'Schilddrüse', 'aliases': ['tsh', 'tsh basal']},
]


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
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', 'µ': 'u', 'γ': 'y'}
    result = str(value or '').strip().lower()
    for source, target in replacements.items():
        result = result.replace(source, target)
    return ' '.join(''.join(char if char.isalnum() else ' ' for char in result).split())


def slug_key(value: str, fallback: str = 'laborwert') -> str:
    """Erzeugt einen stabilen ASCII-Key für neue Parserwerte."""
    key = normalize_text(value).replace(' ', '_')
    return key or fallback


def normalize_ocr_line(value: str) -> str:
    """Glättet OCR-Zeilen, ohne fachliche Werte zu verändern."""
    clean = str(value or '').replace('–', '-').replace('—', '-').replace('−', '-')
    clean = clean.replace('≥', '>=').replace('≤', '<=')
    clean = re.sub(r'(?<=\d)\s*,\s*(?=\d)', ',', clean)
    clean = re.sub(r'(?<=\d)\s*\.\s*(?=\d)', '.', clean)
    return ' '.join(clean.strip().split())


def normalize_unit(value: str) -> str:
    """Normalisiert häufige OCR-Verwechslungen in Einheiten."""
    unit = str(value or '').strip().replace('μ', 'µ')
    unit = unit.replace('/1', '/l').replace('/I', '/l').replace('/|', '/l')
    unit = unit.replace('mmo1', 'mmol').replace('mmoI', 'mmol').replace('mmo|', 'mmol')
    lower = unit.lower()
    mapping = {
        'u/l': 'U/l',
        'u/1': 'U/l',
        'mg/1': 'mg/l',
        'mu/l': 'mU/l',
        'mu/1': 'mU/l',
        '/n1': '/nl',
        '/p1': '/pl',
    }
    return mapping.get(lower, unit)


def known_profiles() -> list[dict]:
    """Liefert bekannte Laborwertprofile sortiert nach Alias-Spezifität."""
    return sorted(KNOWN_ANALYTE_PROFILES, key=lambda item: max(len(normalize_text(alias)) for alias in item['aliases']), reverse=True)


def resolve_known_profile(display_name: str) -> tuple[str, str, str] | None:
    """Erkennt häufige Laborwerte auch bei OCR-Schreibvarianten."""
    normalized = normalize_text(display_name)
    for profile in known_profiles():
        aliases = {normalize_text(alias) for alias in profile['aliases']}
        if normalized in aliases:
            return profile['key'], profile['display'], profile['group']
    return None


def parser_aliases() -> list[tuple[LabAnalyte, list[str]]]:
    """Lädt Laborwert-Aliasse aus der Datenbank."""
    analytes = LabAnalyte.objects.select_related('group').filter(is_active=True)
    result = []
    for analyte in analytes:
        aliases = {analyte.display_name, analyte.key.replace('_', ' '), *[str(alias) for alias in analyte.aliases]}
        result.append((analyte, sorted({normalize_text(alias) for alias in aliases if alias}, key=len, reverse=True)))
    return result


def resolve_analyte(display_name: str, aliases: list[tuple[LabAnalyte, list[str]]]) -> tuple[str, str, str | None] | None:
    """Findet einen vorhandenen Laborwert anhand von Anzeigename, Datenbankalias oder OCR-Profil."""
    normalized = normalize_text(display_name)

    special_key = SPECIAL_ALIASES.get(normalized)
    if special_key:
        for analyte, _ in aliases:
            if analyte.key == special_key:
                return analyte.key, analyte.display_name, analyte.group.name

    for analyte, names in aliases:
        if normalized in names:
            return analyte.key, analyte.display_name, analyte.group.name

    known = resolve_known_profile(display_name)
    if known:
        return known

    if special_key:
        return special_key, display_name.strip(), None

    return None


def parse_reference(reference: str) -> tuple[Decimal, Decimal]:
    """Liest Referenzbereiche wie `13,5 - 17,5`, `< 5,0`, `> 30` oder `>= 60`."""
    clean = str(reference or '').strip().replace('–', '-').replace('≥', '>=').replace('≤', '<=')
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


def confidence_for_row(analyte_key: str, unit: str, reference: str, source: str = 'ocr') -> int:
    """Bewertet die Parserqualität anhand erkannter Strukturmerkmale."""
    has_unit = bool(str(unit or '').strip())
    has_reference = bool(str(reference or '').strip())
    base = 82 if source == 'ocr' else 88

    if has_unit:
        base += 5
    if has_reference:
        base += 6
    if analyte_key in REVIEW_ALIAS_KEYS:
        base -= 8
    if not has_reference:
        base -= 12

    return max(55, min(base, 97))


def should_skip_line(line: str) -> bool:
    """Filtert Kopfzeilen, Fußnoten und erklärende Textblöcke aus."""
    normalized = normalize_text(line)
    return any(fragment in normalized for fragment in SKIP_LINE_FRAGMENTS)


def build_parsed_value(name: str, value: str, unit: str, reference: str, original_text: str, aliases: list[tuple[LabAnalyte, list[str]]], fallback_group: str = 'Importierte Werte', source: str = 'ocr') -> ParsedLabValue | None:
    """Baut aus einer erkannten Tabellenzeile einen Parser-Kandidaten."""
    resolved = resolve_analyte(name, aliases)
    analyte_key = resolved[0] if resolved else slug_key(name)
    display_name = resolved[1] if resolved else name.strip()
    group_name = resolved[2] if resolved and resolved[2] else fallback_group
    normalized_unit = normalize_unit(unit)
    reference_min, reference_max = parse_reference(reference)
    confidence = confidence_for_row(analyte_key, normalized_unit, reference, source)

    if not display_name or not re.search(r'\d', value):
        return None

    return ParsedLabValue(analyte_key=analyte_key, display_name=display_name, group_name=group_name, value=to_decimal(value), unit=normalized_unit, reference_min=reference_min, reference_max=reference_max, original_text=original_text, confidence=confidence)


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

        candidate = build_parsed_value(display_name, value_text, unit, reference, f'{group_name} · {display_name} · {value_text} {unit} · Referenz {reference}', aliases, group_name.strip(), 'text')
        if candidate:
            parsed.append(candidate)
        index += 5

    return parsed


def parse_ocr_table_rows(text: str, aliases: list[tuple[LabAnalyte, list[str]]]) -> list[ParsedLabValue]:
    """Parst OCR-Zeilen klassischer Laborbefunde mit Ergebnis, Dimension und Referenzbereich."""
    parsed: list[ParsedLabValue] = []

    for raw_line in text.splitlines():
        line = normalize_ocr_line(raw_line)
        if not line or should_skip_line(line):
            continue

        match = OCR_ROW_PATTERN.match(line)
        if not match:
            continue

        name = match.group('name').strip()
        if should_skip_line(name):
            continue

        resolved = resolve_analyte(name, aliases)
        if not resolved:
            continue

        candidate = build_parsed_value(name, match.group('value'), match.group('unit'), match.group('reference') or '', line, aliases, resolved[2] or 'Importierte Werte', 'ocr')
        if candidate:
            parsed.append(candidate)

    return parsed


def parse_inline_values(text: str, aliases: list[tuple[LabAnalyte, list[str]]]) -> list[ParsedLabValue]:
    """Fallback für einfache zeilenbasierte Laborwerttexte."""
    parsed = []
    for raw_line in text.splitlines():
        line = normalize_ocr_line(raw_line)
        if not line or should_skip_line(line):
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
            unit = normalize_unit(match.group('unit') or match.group('ref_unit') or '')
            reference_min = to_decimal(match.group('ref_low'))
            reference_max = to_decimal(match.group('ref_high'), Decimal('999999'))
            confidence = 92 if reference_max != Decimal('999999') and unit else 72
            parsed.append(ParsedLabValue(analyte.key, analyte.display_name, analyte.group.name, to_decimal(match.group('value')), unit, reference_min, reference_max, line, confidence))
            break
    return parsed


def parse_lab_values(text: str) -> list[ParsedLabValue]:
    """Erkennt Laborwert-Zeilen anhand von Tabellenstruktur, OCR-Tabellen und gepflegten Aliassen."""
    aliases = parser_aliases()
    table_values = parse_table_lines(text, aliases)
    if table_values:
        return table_values

    ocr_values = parse_ocr_table_rows(text, aliases)
    if ocr_values:
        return ocr_values

    return parse_inline_values(text, aliases)
