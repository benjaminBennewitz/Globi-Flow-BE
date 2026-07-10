# apps/reports/tests_translation.py

"""Tests für Backend-Berichtsvorlage und sichere Segmentübersetzung."""

from django.test import SimpleTestCase

from apps.reports.report_template import get_report_template
from apps.reports.translation import _translate_structure, _translate_text, _validate_translation


class FakeTranslator:
    """Deterministischer Übersetzer für isolierte Unit-Tests."""

    def translate(self, text: str) -> str:
        """Kennzeichnet jeden tatsächlich übersetzten Textabschnitt."""
        return f"EN:{text}"


class ReportTranslationTests(SimpleTestCase):
    """Prüft Vorlage, Segmentierung und Berichtsintegrität ohne Argos-Modell."""

    def test_report_template_contains_all_main_sections(self) -> None:
        """Prüft zentrale Überschriften der druckbaren Berichtsvorlage."""
        template = get_report_template()

        self.assertEqual(template["sprache"], "de")
        self.assertEqual(template["bericht"]["haupttitel"], "Blutwerte verständlich zusammengefasst")
        self.assertEqual(template["bericht"]["fragenTitel"], "Fragen für das Arztgespräch")
        self.assertEqual(template["statusLabels"]["hoch"], "ERHÖHT")

    def test_template_is_translated_recursively(self) -> None:
        """Prüft, dass auch verschachtelte Überschriften übersetzt werden."""
        translated = _translate_structure(get_report_template(), FakeTranslator(), {})

        self.assertEqual(translated["sprache"], "de")
        self.assertEqual(translated["bericht"]["marke"], "Globi Flow")
        self.assertEqual(translated["bericht"]["haupttitel"], "EN:Blutwerte verständlich zusammengefasst")
        self.assertEqual(translated["statusLabels"]["normal"], "EN:UNAUFFÄLLIG")


    def test_interface_texts_remain_german(self) -> None:
        """Prüft, dass nur Texte innerhalb der Druckvorschau übersetzt werden."""
        template = get_report_template()
        translated = {**template}
        translated["bericht"] = _translate_structure(template["bericht"], FakeTranslator(), {})
        translated["statusLabels"] = _translate_structure(template["statusLabels"], FakeTranslator(), {})
        translated["prioritaetLabels"] = _translate_structure(template["prioritaetLabels"], FakeTranslator(), {})

        self.assertEqual(translated["oberflaeche"]["seitentitel"], "DIN-A4 Berichtsvorschau")
        self.assertEqual(translated["oberflaeche"]["drucken"], "Drucken")
        self.assertEqual(translated["bericht"]["haupttitel"], "EN:Blutwerte verständlich zusammengefasst")
        self.assertEqual(translated["statusLabels"]["normal"], "EN:UNAUFFÄLLIG")

    def test_glossary_and_numbers_never_become_tokens(self) -> None:
        """Prüft Glossarbegriffe und Messwerte ohne sichtbare Hilfstokens."""
        translated = _translate_text(
            "Der Blutzucker beträgt 5,6 mmol/l.",
            FakeTranslator(),
            {"Blutzucker": "blood glucose"},
        )

        self.assertIn("blood glucose", translated)
        self.assertIn("5,6", translated)
        self.assertNotIn("GLBGLOSSARY", translated)
        self.assertNotIn("GLBPROTECTED", translated)

    def test_integrity_validation_accepts_unchanged_measurements(self) -> None:
        """Prüft unveränderte technische Laborwertfelder."""
        original = {
            "werte": [{"key": "glucose", "wert": 5.6, "einheit": "mmol/l", "referenzMin": 4.1, "referenzMax": 6.1, "status": "normal", "trend": "stabil", "verlauf": [5.4, 5.6]}],
            "empfehlungen": [],
            "fragen": [],
        }
        translated = {
            "werte": [{"key": "glucose", "wert": 5.6, "einheit": "mmol/l", "referenzMin": 4.1, "referenzMax": 6.1, "status": "normal", "trend": "stabil", "verlauf": [5.4, 5.6]}],
            "empfehlungen": [],
            "fragen": [],
        }

        _validate_translation(original, translated)
