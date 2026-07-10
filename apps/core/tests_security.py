# apps/core/tests_security.py

"""Security-Tests für zentrale Eingabevalidierung."""

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.core.input_validation import clean_name, clean_text


class InputValidationSecurityTests(SimpleTestCase):
    """Prüft XSS-Fragmente und erlaubte medizinische Texte."""

    def test_script_fragment_is_rejected(self):
        """Lehnt Script-Tags serverseitig ab."""
        with self.assertRaises(ValidationError):
            clean_text("Hinweis <script>alert(1)</script>", field="hinweis", max_length=500)

    def test_event_handler_is_rejected(self):
        """Lehnt HTML-Eventhandler serverseitig ab."""
        with self.assertRaises(ValidationError):
            clean_text('Text onerror="alert(1)"', field="hinweis", max_length=500)

    def test_normal_medical_text_is_preserved(self):
        """Erhält normale Interpunktion in medizinischen Texten."""
        self.assertEqual(clean_text("Kontrolle in 4–6 Wochen; nüchtern.", field="hinweis", max_length=500), "Kontrolle in 4–6 Wochen; nüchtern.")

    def test_name_uses_allowlist(self):
        """Akzeptiert einen realistischen Testnamen und blockiert Markup."""
        self.assertEqual(clean_name("Müller-Testperson", field="name"), "Müller-Testperson")
        with self.assertRaises(ValidationError):
            clean_name("<img src=x>", field="name")
