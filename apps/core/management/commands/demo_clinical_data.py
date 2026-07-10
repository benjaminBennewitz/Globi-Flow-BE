# apps/core/management/commands/demo_clinical_data.py

"""Fiktive, nicht medizinisch verwendbare Datensätze für den Demo-Reset."""

from datetime import date
from decimal import Decimal
from typing import Any

from apps.labs.models import LabValue
from apps.patients.models import Patient

DISCLAIMER = 'Diese Demo-Auswertung ersetzt keine ärztliche Diagnose. Die Daten sind fiktiv und dienen ausschließlich zum Testen des lokalen Workflows.'

DEMO_PATIENTS = [
    {
        'public_id': 'patient-demo-01',
        'number': 'TP-2026-001',
        'first_name': 'Mara',
        'last_name': 'Hoffmann',
        'birth_date': date(1989, 4, 12),
        'sex': Patient.Sex.FEMALE,
        'weight_kg': Decimal('68.00'),
        'height_cm': 169,
        'lifestyle': 'wechselnde Belastung, wenig Schlaf, vegetarische Ernährung mit unregelmäßiger Supplementierung',
        'non_smoker': True,
        'drinks_alcohol': False,
        'uses_drugs': False,
        'context': 'schwankender Verlauf mit Entzündung, Eisenmangel, Schilddrüse und Mikronährstoffen',
        'source': Patient.Source.DEMO,
        'status': Patient.Status.REPORT,
        'note': 'Fiktive Testperson mit auffälligem Verlauf für komplexe Analyseansichten.',
    },
    {
        'public_id': 'patient-demo-02',
        'number': 'TP-2026-002',
        'first_name': 'Jonas',
        'last_name': 'Keller',
        'birth_date': date(1995, 9, 24),
        'sex': Patient.Sex.MALE,
        'weight_kg': Decimal('82.00'),
        'height_cm': 184,
        'lifestyle': 'Ausdauersport und Krafttraining, hohe Aktivität, proteinreiche Ernährung',
        'non_smoker': True,
        'drinks_alcohol': False,
        'uses_drugs': False,
        'context': 'Sportprofil mit unauffälligem Verlauf und trainingsrelevanten Laborwerten',
        'source': Patient.Source.HISTORY,
        'status': Patient.Status.REPORT,
        'note': 'Fiktiver Sportler mit stabilen Verlaufswerten.',
    },
    {
        'public_id': 'patient-demo-03',
        'number': 'TP-2026-003',
        'first_name': 'Lea',
        'last_name': 'Sommer',
        'birth_date': date(1978, 1, 7),
        'sex': Patient.Sex.FEMALE,
        'weight_kg': Decimal('74.00'),
        'height_cm': 171,
        'lifestyle': 'Büroalltag, moderater Stress, beginnende Ernährungsumstellung',
        'non_smoker': False,
        'drinks_alcohol': True,
        'uses_drugs': False,
        'context': 'leichte Auffälligkeiten mit Verbesserung im Verlauf',
        'source': Patient.Source.OCR,
        'status': Patient.Status.REPORT,
        'note': 'Fiktiver Verlauf mit abklingender Entzündung und besserer Stoffwechsellage.',
    },
    {
        'public_id': 'patient-demo-04',
        'number': 'TP-2026-004',
        'first_name': 'Emil',
        'last_name': 'Brandt',
        'birth_date': date(1964, 6, 30),
        'sex': Patient.Sex.MALE,
        'weight_kg': Decimal('78.00'),
        'height_cm': 176,
        'lifestyle': 'regelmäßige Bewegung, ausgewogene Ernährung, Nichtraucher',
        'non_smoker': True,
        'drinks_alcohol': False,
        'uses_drugs': False,
        'context': 'sehr gesunder stabiler Verlauf',
        'source': Patient.Source.HISTORY,
        'status': Patient.Status.REPORT,
        'note': 'Fiktiver gesunder Verlauf als Positivbeispiel.',
    },
    {
        'public_id': 'patient-demo-05',
        'number': 'TP-2026-005',
        'first_name': 'Nora',
        'last_name': 'Weber',
        'birth_date': date(1991, 11, 3),
        'sex': Patient.Sex.FEMALE,
        'weight_kg': None,
        'height_cm': None,
        'lifestyle': 'nicht angegeben',
        'non_smoker': False,
        'drinks_alcohol': False,
        'uses_drugs': False,
        'context': 'noch keine Demo-Befunde angelegt',
        'source': Patient.Source.MANUAL,
        'status': Patient.Status.EMPTY,
        'note': 'Leere fiktive Testperson für Empty-State-Tests.',
    },
    {
        'public_id': 'patient-demo-06',
        'number': 'TP-2026-006',
        'first_name': 'Melanie',
        'last_name': 'Schneider',
        'birth_date': date(1984, 8, 18),
        'sex': Patient.Sex.FEMALE,
        'weight_kg': None,
        'height_cm': None,
        'lifestyle': 'nicht angegeben',
        'non_smoker': False,
        'drinks_alcohol': False,
        'uses_drugs': False,
        'context': 'noch keine Demo-Befunde angelegt',
        'source': Patient.Source.MANUAL,
        'status': Patient.Status.EMPTY,
        'note': 'Leere fiktive Testperson für Upload- und Anlage-Tests.',
    },
]

GROUPS = {
    'blutbild': ('Blutbild', 10),
    'entzuendung': ('Entzündung', 20),
    'stoffwechsel': ('Stoffwechsel', 30),
    'lipide': ('Fettstoffwechsel', 40),
    'niere': ('Niere', 50),
    'leber': ('Leber', 60),
    'schilddruese': ('Schilddrüse', 70),
    'mineralien': ('Mineralien', 80),
    'spurenelemente': ('Spurenelemente', 90),
    'vitamine': ('Vitamine', 100),
    'sport': ('Sportmedizin', 110),
    'hormone': ('Hormone', 120),
}

ANALYTES = {
    'haemoglobin': ('Hämoglobin', 'blutbild', 'g/dl', Decimal('12.0'), Decimal('17.5')),
    'erythrozyten': ('Erythrozyten', 'blutbild', 'Mio/µl', Decimal('4.1'), Decimal('5.9')),
    'leukozyten': ('Leukozyten', 'blutbild', 'Tsd/µl', Decimal('4.0'), Decimal('10.0')),
    'thrombozyten': ('Thrombozyten', 'blutbild', 'Tsd/µl', Decimal('150'), Decimal('400')),
    'crp': ('CRP', 'entzuendung', 'mg/l', Decimal('0'), Decimal('5')),
    'glukose': ('Glukose nüchtern', 'stoffwechsel', 'mg/dl', Decimal('70'), Decimal('99')),
    'hba1c': ('HbA1c', 'stoffwechsel', '%', Decimal('4.8'), Decimal('5.6')),
    'insulin': ('Insulin nüchtern', 'stoffwechsel', 'µU/ml', Decimal('2'), Decimal('15')),
    'ldl': ('LDL-Cholesterin', 'lipide', 'mg/dl', Decimal('0'), Decimal('115')),
    'hdl': ('HDL-Cholesterin', 'lipide', 'mg/dl', Decimal('45'), Decimal('90')),
    'triglyzeride': ('Triglyzeride', 'lipide', 'mg/dl', Decimal('0'), Decimal('150')),
    'kreatinin': ('Kreatinin', 'niere', 'mg/dl', Decimal('0.55'), Decimal('1.20')),
    'egfr': ('eGFR', 'niere', 'ml/min', Decimal('60'), Decimal('140')),
    'harnstoff': ('Harnstoff', 'niere', 'mg/dl', Decimal('10'), Decimal('50')),
    'alt': ('ALT', 'leber', 'U/l', Decimal('0'), Decimal('45')),
    'ast': ('AST', 'leber', 'U/l', Decimal('0'), Decimal('40')),
    'ggt': ('GGT', 'leber', 'U/l', Decimal('0'), Decimal('55')),
    'tsh': ('TSH', 'schilddruese', 'mIU/l', Decimal('0.4'), Decimal('4.0')),
    'ft3': ('fT3', 'schilddruese', 'pg/ml', Decimal('2.0'), Decimal('4.4')),
    'ft4': ('fT4', 'schilddruese', 'ng/dl', Decimal('0.9'), Decimal('1.7')),
    'ferritin': ('Ferritin', 'mineralien', 'ng/ml', Decimal('30'), Decimal('300')),
    'vitamin_d': ('Vitamin D', 'vitamine', 'ng/ml', Decimal('30'), Decimal('70')),
    'magnesium': ('Magnesium', 'mineralien', 'mmol/l', Decimal('0.75'), Decimal('1.05')),
    'kalium': ('Kalium', 'mineralien', 'mmol/l', Decimal('3.5'), Decimal('5.1')),
    'natrium': ('Natrium', 'mineralien', 'mmol/l', Decimal('135'), Decimal('145')),
    'zink': ('Zink', 'spurenelemente', 'µg/dl', Decimal('70'), Decimal('120')),
    'selen': ('Selen', 'spurenelemente', 'µg/l', Decimal('80'), Decimal('150')),
    'ck': ('Kreatinkinase', 'sport', 'U/l', Decimal('0'), Decimal('190')),
    'testosteron': ('Testosteron', 'hormone', 'ng/ml', Decimal('2.5'), Decimal('8.5')),
}

REPORT_DATES = [date(2025, 9, 18), date(2025, 12, 16),
                date(2026, 3, 14), date(2026, 6, 12)]

VALUE_SERIES = {
    'patient-demo-04': {
        'haemoglobin': [14.8, 14.9, 15.0, 15.1], 'erythrozyten': [4.9, 5.0, 5.0, 5.1], 'leukozyten': [5.8, 5.6, 5.7, 5.5], 'thrombozyten': [236, 231, 229, 225], 'crp': [1.3, 1.0, 0.9, 0.8],
        'glukose': [88, 86, 85, 84], 'hba1c': [5.2, 5.1, 5.1, 5.0], 'ldl': [101, 96, 92, 88], 'hdl': [59, 61, 62, 64], 'triglyzeride': [118, 108, 96, 90],
        'kreatinin': [0.92, 0.90, 0.91, 0.89], 'egfr': [91, 93, 92, 95], 'alt': [24, 22, 21, 20], 'ast': [23, 22, 21, 21], 'ggt': [28, 25, 23, 22],
        'tsh': [1.8, 1.7, 1.6, 1.5], 'ferritin': [104, 111, 116, 121], 'vitamin_d': [37, 42, 45, 48], 'magnesium': [0.86, 0.88, 0.89, 0.90], 'kalium': [4.3, 4.2, 4.3, 4.4],
    },
    'patient-demo-02': {
        'haemoglobin': [15.2, 15.4, 15.5, 15.6], 'erythrozyten': [5.1, 5.2, 5.2, 5.3], 'leukozyten': [5.4, 5.5, 5.3, 5.2], 'thrombozyten': [220, 218, 216, 214], 'crp': [0.8, 0.9, 1.1, 0.7],
        'glukose': [83, 82, 84, 81], 'hba1c': [5.0, 5.0, 4.9, 4.9], 'ldl': [96, 92, 89, 86], 'hdl': [62, 64, 65, 66], 'triglyzeride': [74, 71, 68, 65],
        'kreatinin': [1.05, 1.08, 1.10, 1.12], 'egfr': [96, 94, 93, 92], 'harnstoff': [32, 34, 35, 36], 'alt': [28, 29, 27, 26], 'ast': [31, 32, 30, 29], 'ggt': [19, 18, 17, 17],
        'ferritin': [82, 87, 91, 96], 'vitamin_d': [34, 39, 44, 49], 'magnesium': [0.84, 0.86, 0.88, 0.90], 'kalium': [4.4, 4.5, 4.6, 4.5], 'ck': [148, 162, 176, 184], 'testosteron': [5.4, 5.6, 5.7, 5.8],
    },
    'patient-demo-03': {
        'haemoglobin': [12.2, 12.4, 12.8, 13.2], 'erythrozyten': [4.2, 4.3, 4.4, 4.5], 'leukozyten': [10.8, 9.8, 8.2, 6.4], 'thrombozyten': [390, 360, 330, 286], 'crp': [15.5, 11.2, 6.8, 3.4],
        'glukose': [101, 98, 94, 90], 'hba1c': [5.7, 5.6, 5.5, 5.4], 'ldl': [124, 119, 112, 106], 'hdl': [46, 48, 51, 54], 'triglyzeride': [168, 154, 139, 121],
        'kreatinin': [0.83, 0.82, 0.80, 0.79], 'egfr': [86, 88, 91, 94], 'alt': [49, 43, 35, 29], 'ast': [41, 36, 31, 27], 'ggt': [46, 41, 35, 29],
        'tsh': [2.6, 2.3, 2.0, 1.8], 'ferritin': [26, 31, 38, 48], 'vitamin_d': [24, 28, 34, 39], 'magnesium': [0.73, 0.77, 0.81, 0.86], 'zink': [66, 72, 79, 88],
    },
    'patient-demo-01': {
        'haemoglobin': [12.9, 11.8, 12.4, 10.9], 'erythrozyten': [4.3, 4.0, 4.2, 3.8], 'leukozyten': [8.6, 11.4, 7.8, 12.1], 'thrombozyten': [330, 405, 355, 428], 'crp': [9.8, 28.6, 12.4, 34.2],
        'glukose': [96, 111, 101, 118], 'hba1c': [5.5, 5.8, 5.7, 6.1], 'insulin': [11, 17, 14, 21], 'ldl': [128, 146, 132, 158], 'hdl': [48, 43, 46, 40], 'triglyzeride': [156, 205, 172, 238],
        'kreatinin': [0.82, 0.88, 0.84, 0.91], 'egfr': [91, 86, 89, 82], 'harnstoff': [28, 35, 31, 39], 'alt': [38, 61, 44, 76], 'ast': [35, 49, 39, 58], 'ggt': [44, 72, 51, 88],
        'tsh': [3.9, 5.8, 4.6, 7.2], 'ft3': [2.8, 2.4, 2.6, 2.1], 'ft4': [1.1, 0.96, 1.0, 0.84], 'ferritin': [34, 22, 28, 16], 'vitamin_d': [28, 21, 25, 18],
        'magnesium': [0.78, 0.70, 0.75, 0.68], 'kalium': [4.1, 3.8, 4.0, 3.6], 'natrium': [139, 137, 138, 136], 'zink': [73, 61, 68, 55], 'selen': [84, 72, 78, 66],
    },
}

REPORT_NAMES = {
    'patient-demo-01': ['jahresvergleich-2025.pdf', 'mikronaehrstoff-kontrolle-2025.pdf', 'verlauf-q1-demo.pdf', 'testdaten-laborbefund-optimiert.pdf'],
    'patient-demo-02': ['sport-basis-2025.pdf', 'sport-check-winter.pdf', 'sport-kontrolle-q1.pdf', 'sport-labor-juni-2026.pdf'],
    'patient-demo-03': ['scan-kontrolle-2025.pdf', 'ocr-labor-winter.pdf', 'scan-laborbefund-ocr-demo.pdf', 'kontrolle-verbesserung-juni.pdf'],
    'patient-demo-04': ['lipide-basis-2025.pdf', 'gesundheitscheck-winter.pdf', 'lipide-kontrolle-q1.pdf', 'lipide-verlauf-demo.pdf'],
}

REPORT_SUMMARIES = {
    'patient-demo-01': ('Auffälliger, schwankender Verlauf', 'Mehrere Werte zeigen wiederkehrende Auffälligkeiten. Besonders Entzündung, Eisenstatus, Schilddrüse, Leberwerte, Fettstoffwechsel und Mikronährstoffe sollten ärztlich eingeordnet werden.'),
    'patient-demo-02': ('Unauffälliges Sportprofil', 'Die Werte sind insgesamt stabil. Trainingsnahe Werte wie CK und Kreatinin liegen im erwartbaren Bereich und sollten immer im Kontext der Belastung betrachtet werden.'),
    'patient-demo-03': ('Leichte Auffälligkeiten mit Verbesserung', 'Der Verlauf zeigt eine rückläufige Entzündung und verbesserte Stoffwechsel- und Mikronährstoffwerte. Eine ärztliche Verlaufskontrolle bleibt sinnvoll.'),
    'patient-demo-04': ('Sehr stabiler gesunder Verlauf', 'Die Werte sind überwiegend unauffällig und zeigen eine stabile bis leicht verbesserte Entwicklung über mehrere Befunde.'),
}


def slug(value: str) -> str:
    """Erzeugt einen stabilen ASCII-Schlüssel."""
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
                    'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss', 'µ': 'u'}
    result = value.strip().lower()
    for source, target in replacements.items():
        result = result.replace(source.lower(), target.lower())
    return '-'.join(''.join(char if char.isalnum() else ' ' for char in result).split())


def decimal(value: Any) -> Decimal:
    """Wandelt numerische Seed-Werte sicher in Decimal um."""
    return Decimal(str(value).replace(',', '.'))


def value_status(value: Decimal, lower: Decimal, upper: Decimal) -> str:
    """Berechnet den Laborwertstatus anhand des Referenzbereichs."""
    if value < lower:
        return LabValue.Status.LOW
    if value > upper:
        return LabValue.Status.HIGH
    return LabValue.Status.NORMAL


def value_priority(status: str, key: str) -> str:
    """Leitet eine einfache Priorität ab."""
    if status == LabValue.Status.NORMAL:
        return LabValue.Priority.LOW
    if key in {'crp', 'tsh', 'ft4', 'haemoglobin', 'ferritin', 'alt', 'ggt', 'hba1c'}:
        return LabValue.Priority.HIGH
    return LabValue.Priority.MEDIUM
