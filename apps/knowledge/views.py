# apps/knowledge/views.py

"""API-Views für die kontrollierte Wissensbasis."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
import re
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.knowledge.models import KnowledgeEntry, KnowledgeSource, KnowledgeVersion
from apps.knowledge.presenters import knowledge_to_frontend
from apps.knowledge.services import normalize_chart_color, reset_default_knowledge
from apps.labs.models import LabAnalyte, LabGroup




def normalize_source_date(value: str) -> str:
    """Normalisiert Quellenstände auf MM.JJJJ, sofern Monat und Jahr erkennbar sind."""
    cleaned = str(value or '').strip()
    if not cleaned:
        return ''

    iso_match = re.match(r'^(\d{4})-(\d{1,2})(?:-\d{1,2})?$', cleaned)
    if iso_match:
        return f'{int(iso_match.group(2)):02d}.{iso_match.group(1)}'

    german_match = re.match(r'^(?:\d{1,2}\.)?(\d{1,2})\.(\d{4})$', cleaned)
    if german_match:
        return f'{int(german_match.group(1)):02d}.{german_match.group(2)}'

    compact_match = re.match(r'^(\d{1,2})/(\d{4})$', cleaned)
    if compact_match:
        return f'{int(compact_match.group(1)):02d}.{compact_match.group(2)}'

    return cleaned

def slug(value: str, fallback: str = 'neue_kategorie') -> str:
    """Erzeugt einfache Slugs für fachliche Keys."""
    clean_value = str(value or fallback).strip().lower().replace(' ', '_').replace('-', '_')
    return ''.join(char for char in clean_value if char.isalnum() or char == '_') or fallback


def knowledge_queryset():
    """Lädt Wissenseinträge mit Quellen und Versionen performant."""
    return KnowledgeEntry.objects.select_related('analyte__group').prefetch_related('sources', 'versions')


def ensure_analyte(data: dict, existing: LabAnalyte | None = None) -> LabAnalyte:
    """Lädt oder erstellt den Laborwert für einen Wissenseintrag."""
    category_name = str(data.get('kategorie') or (existing.group.name if existing else 'Neue Kategorie')).strip() or 'Neue Kategorie'
    group, _ = LabGroup.objects.get_or_create(key=slug(category_name), defaults={'name': category_name})
    key = slug(data.get('laborwertKey') or (existing.key if existing else 'neuer_laborwert'), 'neuer_laborwert')
    display_name = str(data.get('anzeigename') or (existing.display_name if existing else 'Neuer Laborwert')).strip() or 'Neuer Laborwert'
    if existing:
        conflict = LabAnalyte.objects.filter(key=key).exclude(id=existing.id).first()
        if conflict:
            return conflict
        existing.key = key
        existing.display_name = display_name
        existing.group = group
        existing.save(update_fields=['key', 'display_name', 'group', 'updated_at'])
        return existing
    analyte, _ = LabAnalyte.objects.get_or_create(key=key, defaults={'display_name': display_name, 'group': group, 'aliases': [display_name, key.replace('_', ' ')]})
    return analyte


def sync_sources(entry: KnowledgeEntry, sources: list[dict]) -> None:
    """Synchronisiert Quellen aus dem Frontendformular."""
    if sources is None:
        return
    entry.sources.all().delete()
    for index, source in enumerate(sources, start=1):
        KnowledgeSource.objects.create(public_id=source.get('id') or f'quelle-{entry.id}-{index}', entry=entry, title=source.get('titel', 'Quelle ohne Titel'), source_type=source.get('typ', 'demo'), source_date=normalize_source_date(source.get('stand', '')), reference=source.get('referenz', ''), note=source.get('hinweis', ''))


def update_entry_from_data(entry: KnowledgeEntry, data: dict) -> KnowledgeEntry:
    """Überträgt Frontendfelder auf den normalisierten Wissenseintrag."""
    entry.analyte = ensure_analyte(data, entry.analyte)
    entry.patient_short_text = data.get('patientKurztext', entry.patient_short_text)
    entry.patient_long_text = data.get('patientLangtext', entry.patient_long_text)
    entry.doctor_information = data.get('arztinformation', entry.doctor_information)
    entry.causes_low = data.get('ursachenNiedrig', entry.causes_low)
    entry.causes_high = data.get('ursachenHoch', entry.causes_high)
    entry.influencing_factors = data.get('einflussfaktoren', entry.influencing_factors)
    entry.notes = data.get('hinweise', entry.notes)
    entry.disclaimer = data.get('disclaimer', entry.disclaimer)
    entry.status = data.get('status', entry.status)
    entry.changed_by = data.get('geaendertVon', entry.changed_by) or 'Admin'
    entry.changed_at_label = data.get('geaendertAm', timezone.localdate().strftime('%d.%m.%Y'))
    entry.chart_color = normalize_chart_color(data.get('farbe', entry.chart_color), entry.analyte.key)
    requested_version = data.get('version')
    note = data.get('aenderungsnotiz', '').strip() or 'Text aktualisiert.'
    if requested_version:
        entry.version = max(entry.version, int(requested_version))
    entry.save()
    KnowledgeVersion.objects.get_or_create(entry=entry, version=entry.version, defaults={'date_label': entry.changed_at_label or timezone.localdate().strftime('%d.%m.%Y'), 'changed_by': entry.changed_by, 'note': note})
    sync_sources(entry, data.get('quellen'))
    return entry


class KnowledgeResetView(APIView):
    """Setzt die Wissensbasis auf den lokalen Mindestbestand zurück."""

    def post(self, request):
        """Erstellt den kontrollierten Mindestbestand neu und gibt ihn zurück."""
        result = reset_default_knowledge()
        entries = knowledge_queryset()
        return Response({'status': 'ok', 'message': 'Wissensbasis wurde auf den Mindestbestand zurückgesetzt.', 'entries': result['entries'], 'analytes': result['analytes'], 'sources': result['sources'], 'items': [knowledge_to_frontend(entry) for entry in entries]}, status=status.HTTP_200_OK)


class KnowledgeListCreateView(APIView):
    """Listet Wissenseinträge und legt Entwürfe an."""

    def get(self, request):
        """Gibt alle Wissenseinträge im Frontendformat aus."""
        entries = knowledge_queryset()
        return Response([knowledge_to_frontend(entry) for entry in entries])

    def post(self, request):
        """Legt einen neuen Wissensentwurf an."""
        analyte = ensure_analyte(request.data)
        entry, created = KnowledgeEntry.objects.get_or_create(analyte=analyte, defaults={'disclaimer': request.data.get('disclaimer', 'Diese Erklärung ersetzt keine ärztliche Diagnose oder Behandlung.'), 'changed_at_label': request.data.get('geaendertAm', timezone.localdate().strftime('%d.%m.%Y')), 'changed_by': request.data.get('geaendertVon', 'Admin')})
        update_entry_from_data(entry, {**request.data, 'version': request.data.get('version', entry.version)})
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(knowledge_to_frontend(knowledge_queryset().get(id=entry.id)), status=status_code)


class KnowledgeDetailView(APIView):
    """Liest, aktualisiert und löscht einzelne Wissenseinträge."""

    def get_object(self, laborwert_key: str) -> KnowledgeEntry:
        """Lädt einen Wissenseintrag mit Quellen und Versionen."""
        return get_object_or_404(knowledge_queryset(), analyte__key=laborwert_key)

    def get(self, request, laborwert_key: str):
        """Gibt einen Wissenseintrag zurück."""
        return Response(knowledge_to_frontend(self.get_object(laborwert_key)))

    def patch(self, request, laborwert_key: str):
        """Aktualisiert Textstand, Quellen und Status."""
        entry = update_entry_from_data(self.get_object(laborwert_key), request.data)
        return Response(knowledge_to_frontend(knowledge_queryset().get(id=entry.id)))

    def delete(self, request, laborwert_key: str):
        """Löscht einen Wissenseintrag."""
        self.get_object(laborwert_key).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
