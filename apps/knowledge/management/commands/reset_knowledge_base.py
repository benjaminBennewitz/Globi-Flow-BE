# apps/knowledge/management/commands/reset_knowledge_base.py

"""Setzt die kontrollierte Wissensbasis auf den Mindestbestand zurück."""

from django.core.management.base import BaseCommand
from apps.knowledge.services import reset_default_knowledge


class Command(BaseCommand):
    """Erstellt den reproduzierbaren Wissensbasis-Mindestbestand."""

    help = 'Setzt die Wissensbasis auf alle Basiswerte des lokalen Laborbefund-Workflows zurück.'

    def handle(self, *args, **options):
        """Führt den Reset aus und gibt eine kurze Statistik aus."""
        result = reset_default_knowledge()
        self.stdout.write(self.style.SUCCESS(f"Wissensbasis zurückgesetzt: {result['entries']} Einträge, {result['sources']} Quellen."))
