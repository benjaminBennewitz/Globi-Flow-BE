# apps/reports/report_template.py

"""Zentrale deutsche Textvorlage für Patientenberichte."""

from __future__ import annotations

from copy import deepcopy


REPORT_TEMPLATE_DE = {
    "sprache": "de",
    "zielsprachen": [
        {"code": "en", "label": "Englisch"},
        {"code": "fr", "label": "Französisch"},
        {"code": "es", "label": "Spanisch"},
        {"code": "tr", "label": "Türkisch"}
    ],
    "oberflaeche": {
        "eyebrow": "Druckfertiger Patientenbericht",
        "seitentitel": "DIN-A4 Berichtsvorschau",
        "seitenbeschreibung": "Freigegebene Laborwerte, Stammdaten, Wissensbasis-Texte und Hinweise als lesbarer Patientenbericht.",
        "vorschauAktualisieren": "Vorschau aktualisieren",
        "drucken": "Drucken",
        "uebersetzungTitel": "Lokale Übersetzung",
        "uebersetzungHinweis": "Erst möglich, wenn auch der Druck freigegeben ist.",
        "uebersetzungAria": "Bericht übersetzen",
        "zielspracheAria": "Zielsprache wählen",
        "deutschAnzeigen": "Deutsch anzeigen",
        "uebersetzen": "Übersetzen",
        "uebersetzungLaeuft": "Übersetzung läuft …",
        "maschinenHinweis": "Maschinelle Übersetzung",
        "maschinenPruefung": "vor Ausgabe fachlich prüfen.",
        "druckGesperrtTitel": "Finaler Druck noch gesperrt",
        "druckGesperrtText": "Reviewpunkt(e) sind noch nicht freigegeben. Die Vorschau bleibt sichtbar, der finale Druck wird blockiert.",
        "steuerungAria": "Berichtssteuerung",
        "patient": "Patient",
        "befund": "Befund",
        "bericht": "Bericht",
        "keinDatum": "kein Datum",
        "keinBefund": "kein Befund gewählt",
        "freigabecheck": "Freigabecheck",
        "fehlendePatiententexte": "Fehlende Patiententexte",
        "fehlendeWissensbasisAria": "Fehlende Wissensbasis-Texte",
        "detailsSchliessen": "Details schließen",
        "druckvorschauAria": "Druckvorschau",
        "nichtAngegeben": "nicht angegeben",
        "checkPatient": "Patient gewählt",
        "checkBefund": "Befund gewählt",
        "checkReview": "Keine offenen Reviewwerte im Druck",
        "checkWissen": "Wissensbasis-Texte vorhanden",
        "checkDisclaimer": "Disclaimer vorhanden",
        "fehlenderPatiententext": "Patientenkurztext in der Wissensbasis fehlt.",
        "toastUebersetztTitel": "Bericht übersetzt",
        "toastUebersetztText": "Die maschinelle Übersetzung ist jetzt in der Vorschau sichtbar.",
        "toastUebersetzungFehlerTitel": "Übersetzung nicht verfügbar",
        "toastUebersetzungFehlerText": "Lokale Engine oder Sprachmodell prüfen.",
        "toastDruckBlockiertTitel": "Druck blockiert",
        "toastDruckBlockiertText": "Offene Reviewwerte müssen vor dem finalen Patientenbericht freigegeben oder entfernt werden.",
        "toastWissenTitel": "Wissensbasis unvollständig",
        "toastWissenText": "Patiententexte fehlen noch."
    },
    "bericht": {
        "seitenlabel": "Seite",
        "berichtstyp": "Patientenbericht",
        "haupttitel": "Blutwerte verständlich zusammengefasst",
        "berichtLabel": "Bericht",
        "erstelltAm": "erstellt am",
        "marke": "Globi Flow",
        "patient": "Patient",
        "geburtsdatumAlter": "Geburtsdatum / Alter",
        "jahre": "Jahre",
        "koerperdaten": "Körperdaten",
        "bmi": "BMI",
        "befund": "Befund",
        "gesamtueberblick": "Gesamtüberblick",
        "gesamt": "gesamt",
        "unauffaellig": "unauffällig",
        "auffaellig": "auffällig",
        "zuPruefen": "zu prüfen",
        "wertgruppenUebersicht": "Wertgruppen im Überblick",
        "werte": "Werte",
        "empfehlungen": "Empfehlungen",
        "arztgespraechHinweise": "Hinweise für das Arztgespräch",
        "empfehlungenEinleitung": "Die Hinweise helfen bei der Vorbereitung und ersetzen keine ärztliche Diagnose.",
        "ergebnisse": "Ergebnisse",
        "laborwerteTitel": "Laborwerte in verständlicher Form",
        "laborwerteEinleitung": "Die Marker zeigen das Ergebnis im Verhältnis zum jeweiligen Referenzbereich.",
        "referenz": "Referenz",
        "gespraechsvorbereitung": "Gesprächsvorbereitung",
        "fragenTitel": "Fragen für das Arztgespräch",
        "fragenEinleitung": "Die Fragen beziehen sich auf die auffälligen Werte des aktuell ausgewählten Befunds.",
        "quellenBereich": "Quellen und Wissensbasis",
        "quellenTitel": "Hinterlegte Wissensquellen",
        "quellenEinleitung": "Die Quellen zeigen, welche Wissensbasis-Texte für die patientenverständliche Erklärung verwendet wurden.",
        "stand": "Stand",
        "wichtigerHinweis": "Wichtiger Hinweis",
        "abschluss": "Abschluss",
        "abschlussEinleitung": "Für diesen Bericht sind keine zusätzlichen Fragen oder Quellen hinterlegt.",
        "fehlenderPatiententext": "Für diesen Wert ist noch kein Patiententext in der Wissensbasis hinterlegt."
    },
    "statusLabels": {
        "normal": "UNAUFFÄLLIG",
        "niedrig": "NIEDRIG",
        "hoch": "ERHÖHT",
        "review": "PRÜFEN"
    },
    "prioritaetLabels": {
        "normal": "HINWEIS",
        "beachten": "BEACHTEN",
        "wichtig": "WICHTIG"
    }
}


def get_report_template() -> dict:
    """Liefert eine unabhängige Kopie der deutschen Berichtsvorlage."""
    return deepcopy(REPORT_TEMPLATE_DE)
