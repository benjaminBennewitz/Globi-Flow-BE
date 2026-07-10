# apps/imports/parser_definitions.py

"""Statische Parserdefinitionen für lokale Laborbefunde.

Das Modul bündelt reguläre Ausdrücke, bekannte Aliasse und fachliche
Laborwertprofile. Dadurch bleibt die eigentliche Parserpipeline auf die
Erkennung und Normalisierung konzentriert.
"""

import re

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
