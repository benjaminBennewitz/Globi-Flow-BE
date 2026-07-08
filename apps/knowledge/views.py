# apps/knowledge/views.py

"""API-Views für die kontrollierte Wissensbasis."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.knowledge.models import KnowledgeEntry, KnowledgeVersion
from apps.knowledge.presenters import knowledge_to_frontend
from apps.labs.models import LabAnalyte, LabGroup


class KnowledgeListCreateView(APIView):
    """Listet Wissenseinträge und legt Entwürfe an."""

    def get(self, request):
        """Gibt alle Wissenseinträge im Frontendformat aus."""
        entries = KnowledgeEntry.objects.select_related('analyte__group').prefetch_related('sources', 'versions')
        return Response([knowledge_to_frontend(entry) for entry in entries])

    def post(self, request):
        """Legt einen neuen Wissensentwurf an."""
        group, _ = LabGroup.objects.get_or_create(key=request.data.get('kategorie', 'neue_kategorie').lower().replace(' ', '_'), defaults={'name': request.data.get('kategorie', 'Neue Kategorie')})
        analyte, _ = LabAnalyte.objects.get_or_create(key=request.data.get('laborwertKey', 'neuer_laborwert'), defaults={'display_name': request.data.get('anzeigename', 'Neuer Laborwert'), 'group': group})
        entry, _ = KnowledgeEntry.objects.get_or_create(analyte=analyte, defaults={'disclaimer': 'Diese Erklärung ersetzt keine ärztliche Diagnose oder Behandlung.', 'changed_at_label': 'neu'})
        KnowledgeVersion.objects.get_or_create(entry=entry, version=entry.version, defaults={'date_label': entry.changed_at_label or 'neu', 'changed_by': entry.changed_by, 'note': 'Entwurf angelegt.'})
        return Response(knowledge_to_frontend(KnowledgeEntry.objects.prefetch_related('sources', 'versions').get(id=entry.id)), status=status.HTTP_201_CREATED)


class KnowledgeDetailView(APIView):
    """Liest, aktualisiert und löscht einzelne Wissenseinträge."""

    def get_object(self, laborwert_key: str) -> KnowledgeEntry:
        """Lädt einen Wissenseintrag mit Quellen und Versionen."""
        return KnowledgeEntry.objects.select_related('analyte__group').prefetch_related('sources', 'versions').get(analyte__key=laborwert_key)

    def get(self, request, laborwert_key: str):
        """Gibt einen Wissenseintrag zurück."""
        return Response(knowledge_to_frontend(self.get_object(laborwert_key)))

    def patch(self, request, laborwert_key: str):
        """Aktualisiert Textstand und Status."""
        entry = self.get_object(laborwert_key)
        entry.patient_short_text = request.data.get('patientKurztext', entry.patient_short_text)
        entry.patient_long_text = request.data.get('patientLangtext', entry.patient_long_text)
        entry.doctor_information = request.data.get('arztinformation', entry.doctor_information)
        entry.causes_low = request.data.get('ursachenNiedrig', entry.causes_low)
        entry.causes_high = request.data.get('ursachenHoch', entry.causes_high)
        entry.influencing_factors = request.data.get('einflussfaktoren', entry.influencing_factors)
        entry.notes = request.data.get('hinweise', entry.notes)
        entry.disclaimer = request.data.get('disclaimer', entry.disclaimer)
        entry.status = request.data.get('status', entry.status)
        entry.changed_by = request.data.get('geaendertVon', entry.changed_by)
        entry.changed_at_label = request.data.get('geaendertAm', entry.changed_at_label)
        if request.data.get('version') and int(request.data['version']) > entry.version:
            entry.version = int(request.data['version'])
            KnowledgeVersion.objects.get_or_create(entry=entry, version=entry.version, defaults={'date_label': entry.changed_at_label, 'changed_by': entry.changed_by, 'note': request.data.get('aenderungsnotiz', 'Text aktualisiert.')})
        entry.save()
        return Response(knowledge_to_frontend(self.get_object(laborwert_key)))

    def delete(self, request, laborwert_key: str):
        """Löscht einen Wissenseintrag."""
        self.get_object(laborwert_key).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
