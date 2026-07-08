# apps/core/management/commands/cleanup_empty_reports.py

"""Entfernt wirklich leere Testdaten-Befunde ohne Werte und Reviewkandidaten."""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from apps.labs.models import LabReport


class Command(BaseCommand):
    """Löscht nur Befunde, die weder Laborwerte noch Reviewkandidaten enthalten."""

    help = 'Entfernt wirklich leere Laborbefunde aus der lokalen Testdatenbank.'

    def add_arguments(self, parser):
        """Ergänzt Sicherheitsparameter für Vorschau und gezielte Löschung."""
        parser.add_argument('--commit', action='store_true', help='Löscht die gefundenen Befunde wirklich. Ohne Flag erfolgt nur eine Vorschau.')
        parser.add_argument('--public-id', default='', help='Grenzt die Suche auf einen bestimmten Befund ein.')
        parser.add_argument('--patient-id', default='', help='Grenzt die Suche auf eine bestimmte Testperson ein.')
        parser.add_argument('--name-contains', default='', help='Grenzt die Suche auf einen Dateinamen oder Befundnamen ein.')

    def handle(self, *args, **options):
        """Führt eine sichere Vorschau oder Löschung aus."""
        queryset = LabReport.objects.annotate(value_count=Count('values', distinct=True), review_count=Count('review_candidates', distinct=True)).filter(value_count=0, review_count=0).select_related('patient').order_by('patient__display_name', '-report_date')

        public_id = options.get('public_id', '').strip()
        patient_id = options.get('patient_id', '').strip()
        name_contains = options.get('name_contains', '').strip()

        if public_id:
            queryset = queryset.filter(public_id=public_id)
        if patient_id:
            queryset = queryset.filter(patient__public_id=patient_id)
        if name_contains:
            queryset = queryset.filter(Q(name__icontains=name_contains) | Q(public_id__icontains=name_contains))

        count = queryset.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Keine wirklich leeren Befunde gefunden.'))
            return

        for report in queryset:
            self.stdout.write(f'{report.public_id} · {report.patient.display_name} · {report.report_date:%d.%m.%Y} · {report.name}')

        if not options['commit']:
            self.stdout.write(self.style.WARNING(f'{count} wirklich leere Befunde gefunden. Befunde mit offenen Reviewkandidaten werden nicht gelöscht. Zum Löschen erneut mit --commit ausführen.'))
            return

        queryset.delete()
        self.stdout.write(self.style.SUCCESS(f'{count} wirklich leere Befunde gelöscht.'))
