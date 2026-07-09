# apps/knowledge/services.py

"""Seed- und Farblogik für die kontrollierte Wissensbasis."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from django.db import transaction
from django.utils import timezone
from apps.knowledge.models import KnowledgeEntry, KnowledgeSource, KnowledgeVersion
from apps.labs.models import LabAnalyte, LabGroup

DEFAULT_DISCLAIMER = 'Diese Erklärung ersetzt keine ärztliche Diagnose oder Behandlung. Laborwerte müssen immer im persönlichen Kontext ärztlich eingeordnet werden.'
DEMO_SOURCE_TITLE = 'Globi Flow Demo-Wissensbasis'
DEMO_SOURCE_REFERENCE = 'Fiktiver lokaler Seed für Testdaten, OCR-Importe und Patientenberichte.'
COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')

COLOR_PALETTE = [
    '#b91c1c', '#dc2626', '#ea580c', '#d97706', '#ca8a04', '#65a30d', '#16a34a', '#059669',
    '#0d9488', '#0891b2', '#0284c7', '#2563eb', '#4f46e5', '#7c3aed', '#9333ea', '#c026d3',
    '#db2777', '#e11d48', '#be123c', '#9f1239', '#0f766e', '#0369a1', '#1d4ed8', '#4338ca',
    '#6d28d9', '#86198f', '#a21caf', '#be185d', '#92400e', '#166534', '#0f5297', '#475569'
]

GROUPS = {
    'blutbild': ('Blutbild', 10),
    'mineralien': ('Mineralien', 20),
    'fettstoffwechsel': ('Fettstoffwechsel', 30),
    'stoffwechsel': ('Stoffwechsel', 40),
    'eiweissstoffwechsel': ('Eiweißstoffwechsel', 45),
    'leber_galle': ('Leber und Galle', 50),
    'niere': ('Niere', 60),
    'entzuendung': ('Entzündung', 70),
    'schilddruese': ('Schilddrüse', 80),
    'enzyme': ('Enzyme', 90),
    'vitamine': ('Vitamine', 100),
    'spurenelemente': ('Spurenelemente', 110),
    'sport': ('Sportmedizin', 120),
    'hormone': ('Hormone', 130),
}


@dataclass(frozen=True)
class KnowledgeSeed:
    """Beschreibt einen reproduzierbaren Wissensbasis-Eintrag."""

    key: str
    display_name: str
    group_key: str
    color: str
    aliases: tuple[str, ...]
    short_text: str
    long_text: str
    low_causes: str = ''
    high_causes: str = ''
    factors: str = ''


def slug(value: str, fallback: str = 'laborwert') -> str:
    """Erzeugt einen stabilen ASCII-Schlüssel."""
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', 'µ': 'u', 'γ': 'gamma'}
    result = str(value or fallback).strip().lower()
    for source, target in replacements.items():
        result = result.replace(source, target)
    key = '_'.join(''.join(char if char.isalnum() else ' ' for char in result).split())
    return key or fallback


def color_for_key(key: str) -> str:
    """Liefert eine reproduzierbare Fallback-Farbe für einen Laborwert-Key."""
    digest = hashlib.sha256(str(key).encode('utf-8')).hexdigest()
    index = int(digest[:8], 16) % len(COLOR_PALETTE)
    return COLOR_PALETTE[index]


def normalize_chart_color(value: str, key: str = '') -> str:
    """Normalisiert Farbeingaben auf sichere Hex-Werte."""
    cleaned = str(value or '').strip()
    if COLOR_PATTERN.match(cleaned):
        return cleaned.lower()
    return color_for_key(key or 'laborwert')


def general_short_text(name: str) -> str:
    """Erzeugt einen knappen Patiententext für Basiswerte."""
    return f'{name} ist ein Laborwert, der im Zusammenhang mit Referenzbereich, Verlauf und Beschwerden eingeordnet wird.'


def general_long_text(name: str) -> str:
    """Erzeugt einen ausführlicheren Patiententext für Basiswerte."""
    return f'Der Wert {name} hilft dabei, bestimmte Körperfunktionen einzuordnen. Einzelne Abweichungen sind nicht automatisch eine Diagnose. Wichtig sind Verlauf, Begleitwerte, Medikamente, Ernährung und der ärztliche Gesamteindruck.'


DEFAULT_KNOWLEDGE_SEEDS = [
    KnowledgeSeed('leukozyten', 'Leukozyten', 'blutbild', '#2563eb', ('Leukozyten', 'WBC'), 'Leukozyten sind weiße Blutkörperchen und gehören zur Immunabwehr.', 'Leukozyten können bei Infekten, Entzündungen, Stress oder bestimmten Medikamenten verändert sein.', 'Knochenmark, Infekte, Medikamente', 'Infekte, Entzündungen, Stressreaktion', 'Infekte, Kortison, körperliche Belastung'),
    KnowledgeSeed('erythrozyten', 'Erythrozyten', 'blutbild', '#dc2626', ('Erythrozyten', 'RBC'), 'Erythrozyten sind rote Blutkörperchen und transportieren Sauerstoff.', 'Erythrozyten werden zusammen mit Hämoglobin und Hämatokrit betrachtet, um die Sauerstofftransportkapazität einzuschätzen.', 'Blutverlust, Mangelzustände', 'Flüssigkeitsmangel, Höhenaufenthalt', 'Flüssigkeitshaushalt, Training, Rauchen'),
    KnowledgeSeed('haemoglobin', 'Hämoglobin', 'blutbild', '#b91c1c', ('Hämoglobin', 'Haemoglobin', 'Hb'), 'Hämoglobin ist der rote Blutfarbstoff und bindet Sauerstoff.', 'Hämoglobin wird bei der Beurteilung von Blutarmut, Flüssigkeitshaushalt und Sauerstofftransport berücksichtigt.', 'Eisenmangel, Blutverlust, chronische Erkrankungen', 'Flüssigkeitsmangel, Sauerstoffmangelanpassung', 'Eisenstatus, Menstruation, Hydration'),
    KnowledgeSeed('haematokrit', 'Hämatokrit', 'blutbild', '#e11d48', ('Hämatokrit', 'Haematokrit', 'Hkt', 'HCT'), 'Hämatokrit beschreibt den Anteil der Blutzellen am Blutvolumen.', 'Der Hämatokrit wird mit roten Blutkörperchen und Hämoglobin zusammen beurteilt.', 'Blutarmut, Überwässerung', 'Flüssigkeitsmangel, vermehrte rote Blutkörperchen', 'Trinkmenge, Höhenaufenthalt, Training'),
    KnowledgeSeed('mcv', 'MCV', 'blutbild', '#f97316', ('MCV',), 'MCV beschreibt die durchschnittliche Größe der roten Blutkörperchen.', 'MCV hilft bei der Einordnung verschiedener Formen einer Blutarmut.', 'Eisenmangel möglich', 'Vitamin-B12- oder Folatmangel möglich', 'Ernährung, Mangelzustände, Alkohol'),
    KnowledgeSeed('mch', 'MCH', 'blutbild', '#ea580c', ('MCH',), 'MCH beschreibt die durchschnittliche Hämoglobinmenge pro rotem Blutkörperchen.', 'MCH wird gemeinsam mit MCV und MCHC zur Einordnung der roten Blutkörperchen genutzt.', 'Eisenmangel möglich', 'Makrozytäre Veränderungen möglich', 'Eisenstatus, Vitaminstatus'),
    KnowledgeSeed('mchc', 'MCHC', 'blutbild', '#d97706', ('MCHC',), 'MCHC beschreibt die Hämoglobinkonzentration in roten Blutkörperchen.', 'MCHC ist ein zusätzlicher Index des kleinen Blutbilds und wird selten isoliert bewertet.', 'Eisenmangel möglich', 'Messartefakte oder seltene Blutbildveränderungen', 'Probenqualität, Hydration'),
    KnowledgeSeed('thrombozyten', 'Thrombozyten', 'blutbild', '#9333ea', ('Thrombozyten', 'PLT'), 'Thrombozyten sind Blutplättchen und wichtig für die Blutgerinnung.', 'Thrombozyten können bei Entzündung, Blutverlust, Medikamenten oder Gerinnungsthemen verändert sein.', 'Infekte, Medikamente, Gerinnungsthemen', 'Entzündung, Blutverlust, Reaktion des Knochenmarks', 'Infekte, Medikamente, Probenqualität'),
    KnowledgeSeed('natrium', 'Natrium', 'mineralien', '#0284c7', ('Natrium', 'Na'), 'Natrium ist ein wichtiges Blutsalz für Wasserhaushalt, Nerven und Muskeln.', 'Natrium wird immer im Zusammenhang mit Flüssigkeitshaushalt und Medikamenten betrachtet.', 'Flüssigkeitsüberschuss, Verluste, Medikamente', 'Flüssigkeitsmangel, Salzhaushalt', 'Trinkmenge, Diuretika, Erbrechen, Durchfall'),
    KnowledgeSeed('kalium', 'Kalium', 'mineralien', '#16a34a', ('Kalium', 'K'), 'Kalium ist wichtig für Muskeln, Nerven und Herzrhythmus.', 'Kaliumabweichungen sollten sorgfältig geprüft werden, weil sie für Muskeln und Herz relevant sein können.', 'Verluste, Medikamente, Ernährung', 'Nierenfunktion, Medikamente, Zellzerfall', 'Probenqualität, Medikamente, Nierenfunktion'),
    KnowledgeSeed('calcium', 'Calcium', 'mineralien', '#ca8a04', ('Calcium', 'Kalzium', 'Ca'), 'Calcium ist wichtig für Knochen, Muskeln und Nerven.', 'Calcium wird zusammen mit Albumin, Vitamin D, Niere und Hormonsystem eingeordnet.', 'Vitamin-D-Mangel, Albumin, Nebenschilddrüse', 'Nebenschilddrüse, Vitamin D, Medikamente', 'Albumin, Vitamin D, Nierenfunktion'),
    KnowledgeSeed('cholesterin_gesamt', 'Cholesterin gesamt', 'fettstoffwechsel', '#db2777', ('Cholesterin', 'Gesamtcholesterin'), 'Gesamtcholesterin fasst verschiedene Blutfette zusammen.', 'Gesamtcholesterin ist nur zusammen mit LDL, HDL, Triglyceriden und Risikoprofil aussagekräftig.', '', 'Ernährung, Genetik, Stoffwechsel', 'Nüchternstatus, Ernährung, Medikamente'),
    KnowledgeSeed('hdl', 'HDL-Cholesterin', 'fettstoffwechsel', '#059669', ('HDL-Cholesterin', 'HDL Cholesterin', 'HDL'), 'HDL ist ein Cholesterinanteil, der häufig als schützender Fettstoffwechselmarker betrachtet wird.', 'HDL wird im Zusammenhang mit LDL, Triglyceriden und individuellen Risikofaktoren bewertet.', 'Bewegungsmangel, Stoffwechsel, Rauchen', '', 'Sport, Rauchen, Ernährung'),
    KnowledgeSeed('ldl', 'LDL-Cholesterin', 'fettstoffwechsel', '#c026d3', ('LDL-Cholesterin', 'LDL Cholesterin', 'LDL Chol.', 'LDL'), 'LDL ist ein wichtiger Fettstoffwechselwert für die ärztliche Risikoeinschätzung.', 'LDL wird nicht isoliert bewertet, sondern mit Risikofaktoren, HDL, Triglyceriden und Vorgeschichte.', '', 'Ernährung, Genetik, Schilddrüse, Stoffwechsel', 'Nüchternstatus, Ernährung, Medikamente'),
    KnowledgeSeed('ldl_hdl_risiko_index', 'LDL/HDL Risiko Index', 'fettstoffwechsel', '#7c3aed', ('LDL/HDL Risiko Index', 'LDL HDL Risiko Index', 'LDL/HDL'), 'Der LDL/HDL-Index setzt zwei Cholesterinanteile ins Verhältnis.', 'Der Index kann die Fettstoffwechsel-Einordnung ergänzen, ersetzt aber keine individuelle Risikobewertung.', '', 'Ungünstiges Verhältnis von LDL zu HDL', 'Sport, Ernährung, Rauchen, Medikamente'),
    KnowledgeSeed('non_hdl_cholesterin', 'Non-HDL-Cholesterin', 'fettstoffwechsel', '#a21caf', ('Non-HDL-Cholesterin', 'Non HDL Cholesterin'), 'Non-HDL-Cholesterin umfasst mehrere atherogene Cholesterinanteile.', 'Non-HDL kann besonders dann hilfreich sein, wenn Triglyceride mitbetrachtet werden sollen.', '', 'Fettstoffwechselstörung möglich', 'Nüchternstatus, Ernährung, Stoffwechsel'),
    KnowledgeSeed('triglyzeride', 'Triglyceride', 'fettstoffwechsel', '#be185d', ('Triglyceride', 'Triglyzeride', 'TG'), 'Triglyceride sind Blutfette, die stark durch Ernährung und Nüchternstatus beeinflusst werden.', 'Triglyceride werden mit Cholesterinwerten, Ernährung, Alkohol und Stoffwechsel betrachtet.', '', 'Nicht nüchtern, Alkohol, Zuckerstoffwechsel, Genetik', 'Nüchternstatus, Alkohol, Ernährung'),
    KnowledgeSeed('glukose', 'Glukose', 'stoffwechsel', '#0d9488', ('Glucose', 'Glukose', 'Blutzucker'), 'Glukose ist der Blutzuckerwert zum Zeitpunkt der Blutabnahme.', 'Glukose hängt stark von Nüchternstatus, Mahlzeiten, Stress und Stoffwechsel ab.', 'selten relevant ohne Kontext', 'Nicht nüchtern, Stress, Diabetesrisiko', 'Nüchternstatus, Infekt, Stress'),
    KnowledgeSeed('gesamteiweiss', 'Gesamteiweiß', 'eiweissstoffwechsel', '#92400e', ('Gesamteiweiss', 'Gesamteiweiß', 'Total Protein'), 'Gesamteiweiß beschreibt die Summe wichtiger Eiweiße im Blut.', 'Gesamteiweiß wird mit Ernährung, Leber, Niere, Entzündung und Flüssigkeitshaushalt eingeordnet.', 'Ernährung, Leber, Niere, Verdünnung', 'Flüssigkeitsmangel, Entzündung möglich', 'Hydration, Ernährung, Entzündung'),
    KnowledgeSeed('bilirubin_gesamt', 'Bilirubin gesamt', 'leber_galle', '#d97706', ('Bilirubin gesamt', 'Bilirubin'), 'Bilirubin ist ein Abbauprodukt des roten Blutfarbstoffs.', 'Bilirubin kann bei Leber, Galle oder vermehrtem Blutabbau verändert sein.', '', 'Galle, Leber, Blutabbau, Gilbert-Syndrom', 'Nüchternheit, Medikamente, Leberwerte'),
    KnowledgeSeed('ast', 'GOT (ASAT)', 'leber_galle', '#ea580c', ('GOT', 'ASAT', 'AST'), 'GOT/AST ist ein Enzym, das unter anderem in Leber und Muskulatur vorkommt.', 'AST wird zusammen mit ALT, GGT, CK und Beschwerden betrachtet.', '', 'Leberreizung, Muskelbelastung, Medikamente', 'Training, Alkohol, Medikamente'),
    KnowledgeSeed('alt', 'GPT (ALAT)', 'leber_galle', '#dc2626', ('GPT', 'ALAT', 'ALT'), 'GPT/ALT ist ein wichtiger Leberenzymwert.', 'ALT wird mit weiteren Leberwerten, Medikamenten, Alkohol und Stoffwechsel eingeordnet.', '', 'Leberreizung, Fettleber, Medikamente, Infekte', 'Alkohol, Medikamente, Stoffwechsel'),
    KnowledgeSeed('ggt', 'γ-GT', 'leber_galle', '#b45309', ('γ-GT', 'Gamma-GT', 'GGT', 'y-GT'), 'γ-GT ist ein Leber- und Gallenwegsenzym.', 'GGT kann durch Alkohol, Medikamente, Galle oder Stoffwechsel beeinflusst werden.', '', 'Alkohol, Medikamente, Galle, Leberstoffwechsel', 'Alkohol, Medikamente, Übergewicht'),
    KnowledgeSeed('alkalische_phosphatase', 'Alkalische Phosphatase', 'leber_galle', '#ca8a04', ('Alkalische Phosphatase', 'AP', 'ALP'), 'Alkalische Phosphatase ist ein Enzym aus Leber/Galle und Knochenstoffwechsel.', 'AP wird mit GGT, Bilirubin, Knochenstoffwechsel und Alter eingeordnet.', '', 'Galle, Knochenumbau, Wachstum, Medikamente', 'Alter, Knochen, Schwangerschaft'),
    KnowledgeSeed('ldh', 'LDH', 'enzyme', '#6d28d9', ('LDH',), 'LDH ist ein unspezifisches Enzym aus vielen Geweben.', 'LDH wird nur im Zusammenhang mit Symptomen, Probenqualität und weiteren Werten sinnvoll interpretiert.', '', 'Gewebereizung, Hämolyse, Muskelbelastung möglich', 'Probenqualität, Training, Hämolyse'),
    KnowledgeSeed('harnsaeure', 'Harnsäure', 'niere', '#4338ca', ('Harnsäure', 'Harnsaeure', 'Uric Acid'), 'Harnsäure entsteht beim Abbau von Purinen.', 'Harnsäure wird im Kontext von Ernährung, Niere, Gichtneigung und Medikamenten betrachtet.', 'selten relevant ohne Kontext', 'Purine, Alkohol, Niere, Medikamente', 'Ernährung, Alkohol, Nierenfunktion'),
    KnowledgeSeed('harnstoff', 'Harnstoff', 'niere', '#1d4ed8', ('Harnstoff', 'Urea'), 'Harnstoff ist ein Abbauprodukt des Eiweißstoffwechsels.', 'Harnstoff hängt von Eiweißzufuhr, Flüssigkeitshaushalt, Leber und Nierenfunktion ab.', 'Leber, geringe Eiweißzufuhr', 'Flüssigkeitsmangel, Eiweißzufuhr, Niere', 'Hydration, Ernährung'),
    KnowledgeSeed('kreatinin', 'Kreatinin', 'niere', '#0369a1', ('Creatinin', 'Kreatinin', 'Creatinine'), 'Kreatinin ist ein Marker, der zur Einschätzung der Nierenfunktion genutzt wird.', 'Kreatinin wird mit eGFR, Muskelmasse, Hydration und Medikamenten betrachtet.', 'geringe Muskelmasse', 'Nierenfunktion, Muskelmasse, Flüssigkeitshaushalt', 'Training, Muskelmasse, Hydration'),
    KnowledgeSeed('egfr', 'eGFR', 'niere', '#0f766e', ('eGFR', 'GFR'), 'eGFR ist eine berechnete Abschätzung der Nierenfilterleistung.', 'eGFR wird aus Kreatinin und Patientendaten berechnet und dient der Verlaufseinordnung.', 'Nierenfunktion, Alter, Berechnungskontext', '', 'Alter, Kreatinin, Muskelmasse'),
    KnowledgeSeed('crp', 'CRP', 'entzuendung', '#be123c', ('CRP', 'C-reaktives Protein'), 'CRP ist ein Entzündungsmarker.', 'CRP steigt häufig bei Entzündungen oder Infektionen, ist aber nicht spezifisch für eine Ursache.', '', 'Infekt, Entzündung, Gewebereizung', 'Infekte, Operationen, Belastung'),
    KnowledgeSeed('tsh', 'TSH (basal)', 'schilddruese', '#4f46e5', ('TSH', 'TSH basal'), 'TSH ist ein Steuerhormon der Schilddrüse.', 'TSH wird zusammen mit Symptomen und bei Bedarf fT3/fT4 betrachtet.', 'Überfunktion möglich', 'Unterfunktion möglich', 'Tageszeit, Medikamente, Biotin'),
    KnowledgeSeed('ferritin', 'Ferritin', 'mineralien', '#65a30d', ('Ferritin', 'Ferr.'), 'Ferritin spiegelt die Eisenspeicher wider.', 'Ferritin wird im Kontext von Entzündung, Blutbild und Eisenversorgung beurteilt.', 'Eisenmangel, Blutverlust', 'Entzündung, Leber, Eisenüberladung', 'CRP, Infekte, Menstruation'),
    KnowledgeSeed('vitamin_d', 'Vitamin D', 'vitamine', '#eab308', ('Vitamin D', '25-OH-Vit. D', '25 OH Vitamin D'), 'Vitamin D ist wichtig für Knochenstoffwechsel und weitere Körperfunktionen.', 'Vitamin D sollte mit Jahreszeit, Supplementierung und individueller Situation eingeordnet werden.', 'geringe Sonne, Ernährung, Aufnahme', 'Supplementierung', 'Jahreszeit, Supplemente'),
    KnowledgeSeed('magnesium', 'Magnesium', 'mineralien', '#22c55e', ('Magnesium', 'Mg'), 'Magnesium ist wichtig für Muskeln, Nerven und Energiestoffwechsel.', 'Magnesium im Blut zeigt nicht immer die gesamte Versorgungslage, kann aber Hinweise geben.', 'Ernährung, Verluste, Medikamente', 'Supplementierung, Nierenfunktion', 'Sport, Medikamente, Durchfall'),
    KnowledgeSeed('zink', 'Zink', 'spurenelemente', '#84cc16', ('Zink', 'Zn'), 'Zink ist ein Spurenelement für Immunsystem, Haut und Stoffwechsel.', 'Zinkwerte werden im Kontext von Ernährung, Entzündung und Supplementierung eingeordnet.', 'Ernährung, Aufnahme, Entzündung', 'Supplementierung', 'Infekte, Ernährung'),
    KnowledgeSeed('selen', 'Selen', 'spurenelemente', '#14b8a6', ('Selen', 'Se'), 'Selen ist ein Spurenelement mit Bezug zu Schilddrüse und antioxidativen Systemen.', 'Selen sollte nur gezielt und im Kontext weiterer Werte beurteilt werden.', 'Ernährung, Aufnahme', 'Supplementierung', 'Ernährung, Supplemente'),
    KnowledgeSeed('ck', 'Kreatinkinase', 'sport', '#64748b', ('Kreatinkinase', 'CK'), 'CK ist ein Muskelwert, der nach Training deutlich steigen kann.', 'CK wird stark durch körperliche Belastung, Muskelmasse und Verletzungen beeinflusst.', '', 'Training, Muskelbelastung, Verletzung', 'Sport, Injektionen, Muskelarbeit'),
    KnowledgeSeed('testosteron', 'Testosteron', 'hormone', '#475569', ('Testosteron',), 'Testosteron ist ein Sexualhormon und wird stark kontextabhängig bewertet.', 'Testosteron sollte mit Uhrzeit, Symptomen, Alter und weiteren Hormonwerten beurteilt werden.', 'Alter, Stress, Erkrankungen', 'Supplemente oder hormonelle Einflüsse', 'Tageszeit, Medikamente'),
]


def ensure_group(group_key: str) -> LabGroup:
    """Lädt oder erstellt eine Laborwertgruppe ohne Dubletten nach Name."""
    name, sort_order = GROUPS[group_key]
    group = LabGroup.objects.filter(key=group_key).first() or LabGroup.objects.filter(name=name).first()
    if group:
        group.key = group_key
        group.name = name
        group.sort_order = sort_order
        group.save(update_fields=['key', 'name', 'sort_order', 'updated_at'])
        return group
    return LabGroup.objects.create(key=group_key, name=name, sort_order=sort_order)


def ensure_seed_analyte(seed: KnowledgeSeed) -> LabAnalyte:
    """Lädt oder erstellt den Laborwert für einen Seed."""
    group = ensure_group(seed.group_key)
    aliases = sorted({seed.display_name, seed.key.replace('_', ' '), *seed.aliases})
    analyte, _ = LabAnalyte.objects.update_or_create(key=seed.key, defaults={'display_name': seed.display_name, 'group': group, 'aliases': aliases, 'is_active': True})
    return analyte


def build_entry_defaults(seed: KnowledgeSeed) -> dict:
    """Baut die Standardtexte für einen Wissenseintrag."""
    today = timezone.localdate().strftime('%d.%m.%Y')
    return {
        'patient_short_text': seed.short_text or general_short_text(seed.display_name),
        'patient_long_text': seed.long_text or general_long_text(seed.display_name),
        'doctor_information': f'Demo-Wissenseintrag für {seed.display_name}. Fachliche Freigabe und Quellenprüfung bleiben ärztliche Aufgabe.',
        'causes_low': seed.low_causes,
        'causes_high': seed.high_causes,
        'influencing_factors': seed.factors,
        'notes': 'Fester Seedtext für lokale Tests. Keine Diagnose, keine automatische Therapieempfehlung.',
        'disclaimer': DEFAULT_DISCLAIMER,
        'version': 1,
        'status': KnowledgeEntry.Status.RELEASED,
        'changed_by': 'System',
        'changed_at_label': today,
        'chart_color': normalize_chart_color(seed.color, seed.key),
    }


@transaction.atomic
def reset_default_knowledge() -> dict[str, int]:
    """Setzt die Wissensbasis auf den lokalen Mindestbestand zurück."""
    KnowledgeSource.objects.all().delete()
    KnowledgeVersion.objects.all().delete()
    KnowledgeEntry.objects.all().delete()

    for index, seed in enumerate(DEFAULT_KNOWLEDGE_SEEDS, start=1):
        analyte = ensure_seed_analyte(seed)
        entry = KnowledgeEntry.objects.create(analyte=analyte, **build_entry_defaults(seed))
        KnowledgeSource.objects.create(public_id=f'quelle-default-{seed.key}', entry=entry, title=DEMO_SOURCE_TITLE, source_type=KnowledgeSource.SourceType.DEMO, source_date='07.2026', reference=DEMO_SOURCE_REFERENCE, note='Lokaler Mindestbestand für Tests und Patientenberichte.')
        KnowledgeVersion.objects.create(entry=entry, version=1, date_label=entry.changed_at_label, changed_by='System', note=f'Mindestbestand #{index} angelegt.')

    return {'entries': KnowledgeEntry.objects.count(), 'analytes': LabAnalyte.objects.filter(key__in=[seed.key for seed in DEFAULT_KNOWLEDGE_SEEDS]).count(), 'sources': KnowledgeSource.objects.count()}
