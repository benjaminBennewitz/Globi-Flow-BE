# apps/core/views.py

"""Allgemeine API-Views und globale Suche."""

import re
from django.core.management import call_command
from django.db import connection
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.imports.models import ImportJob
from apps.knowledge.models import KnowledgeEntry
from apps.labs.models import LabReport, LabValue, ReviewCandidate
from apps.patients.models import Patient
from apps.reports.models import PatientReport


class HealthView(APIView):
    """Prüft API- und Datenbankverfügbarkeit."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """Liefert einen einfachen Healthcheck.

        Args:
            request: Eingehende DRF-Anfrage mit validierten Query- oder Nutzdaten.
        """
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()

        return Response({'status': 'ok', 'database': 'ok', 'service': 'Globi-Flow-BE'})


class DemoDataResetView(APIView):
    """Setzt die klinischen Demo-Daten reproduzierbar zurück."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """Führt den Demo-Reset aus und liefert aktualisierte Eckdaten zurück.

        Args:
            request: Eingehende DRF-Anfrage mit validierten Query- oder Nutzdaten.

        Side Effects:
            Verändert persistierte Anwendungsdaten innerhalb des beschriebenen Workflows.
        """
        call_command('reset_clinical_demo_data', verbosity=0)
        return Response({
            'status': 'ok',
            'message': 'Demo-Daten wurden zurückgesetzt.',
            'patients': Patient.objects.count(),
            'reports': LabReport.objects.count(),
            'values': LabValue.objects.count(),
            'reviews': ReviewCandidate.objects.count(),
        }, status=status.HTTP_200_OK)


class GlobalSearchView(APIView):
    """Sucht backendseitig über Patienten, Befunde, Werte, Reviews, Importe, Wissen und Berichte."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """Liefert gruppierte globale Suchergebnisse für den Header.

        Args:
            request: Eingehende DRF-Anfrage mit validierten Query- oder Nutzdaten.
        """
        query = normalize_search_query(request.query_params.get('q', ''))

        if len(query) < 2:
            return Response({'query': query, 'total': 0, 'groups': []})

        groups = [
            build_patient_group(query),
            build_lab_report_group(query),
            build_lab_value_group(query),
            build_review_group(query),
            build_import_group(query),
            build_knowledge_group(query),
            build_patient_report_group(query),
        ]
        groups = [group for group in groups if group['items']]
        total = sum(len(group['items']) for group in groups)

        return Response({'query': query, 'total': total, 'groups': groups})


def normalize_search_query(value: str) -> str:
    """Normalisiert eine Suchanfrage defensiv für einfache icontains-Abfragen.

    Args:
        value: Zu verarbeitender Eingabewert.

    Returns:
        Rückgabewert vom Typ ``str``.
    """
    cleaned = str(value or '').strip().lower()
    cleaned = re.sub(r'[<>`"\'\\;]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned[:80]


def search_item(item_id: str, title: str, subtitle: str, badge: str, route: str, icon: str = 'search', patient=None, target_id: str | None = None) -> dict:
    """Erzeugt ein einheitliches Suchergebnis für das Frontend.

    Args:
        item_id: Wert für ``item_id``.
        title: Wert für ``title``.
        subtitle: Wert für ``subtitle``.
        badge: Wert für ``badge``.
        route: Wert für ``route``.
        icon: Wert für ``icon``.
        patient: Betroffene Testperson.
        target_id: Wert für ``target_id``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    item = {'id': item_id, 'title': title, 'subtitle': subtitle, 'badge': badge, 'route': route, 'icon': icon, 'targetId': target_id or item_id}

    if patient:
        item['patientId'] = patient.public_id
        item['patientName'] = patient.display_name

    return item


def result_group(key: str, label: str, route: str, items: list[dict]) -> dict:
    """Erzeugt eine Ergebnisgruppe für die globale Suche.

    Args:
        key: Stabiler fachlicher oder technischer Schlüssel.
        label: Wert für ``label``.
        route: Wert für ``route``.
        items: Zu verarbeitende Sammlung.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    return {'key': key, 'label': label, 'route': route, 'items': items}


def build_patient_group(query: str) -> dict:
    """Sucht Testpersonen nach Name, ID, Kontext, Lebensstil und Notiz.

    Args:
        query: Wert für ``query``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    filters = Q(display_name__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(number__icontains=query) | Q(context__icontains=query) | Q(lifestyle__icontains=query) | Q(note__icontains=query)
    patients = Patient.objects.filter(filters).order_by('display_name')[:8]
    items = [search_item(patient.public_id, patient.display_name, f'{patient.number} · {patient.context or "kein Kontext"}', 'Patient', '/patienten', 'groups', patient=patient) for patient in patients]
    return result_group('patients', 'Patienten', '/patienten', items)


def build_lab_report_group(query: str) -> dict:
    """Sucht Laborbefunde nach Befundname, Patient und Status.

    Args:
        query: Wert für ``query``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    filters = Q(public_id__icontains=query) | Q(name__icontains=query) | Q(status__icontains=query) | Q(patient__display_name__icontains=query) | Q(patient__number__icontains=query)
    reports = LabReport.objects.select_related('patient').filter(filters).order_by('-report_date')[:6]
    items = [search_item(report.public_id, report.name, f'{report.patient.display_name} · {report.report_date:%d.%m.%Y}', 'Befund', '/auswertung', 'monitoring', patient=report.patient) for report in reports]
    return result_group('labReports', 'Laborbefunde', '/auswertung', items)


def build_lab_value_group(query: str) -> dict:
    """Sucht Laborwerte nach Anzeigename, Gruppe, Einheit, Hinweis und Patient.

    Args:
        query: Wert für ``query``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    filters = Q(public_id__icontains=query) | Q(analyte__key__icontains=query) | Q(analyte__display_name__icontains=query) | Q(analyte__group__name__icontains=query) | Q(unit__code__icontains=query) | Q(hint__icontains=query) | Q(original_text__icontains=query) | Q(report__patient__display_name__icontains=query)
    values = LabValue.objects.select_related('analyte__group', 'unit', 'report__patient').filter(filters).order_by('analyte__display_name')[:8]
    items = [search_item(value.public_id, value.analyte.display_name, f'{value.report.patient.display_name} · {value.value:g} {value.unit.code} · {value.status}', 'Laborwert', '/auswertung', 'science', patient=value.report.patient) for value in values]
    return result_group('labValues', 'Laborwerte', '/auswertung', items)


def build_review_group(query: str) -> dict:
    """Sucht Review-Kandidaten nach erkanntem Wert, Laborwert und Patient.

    Args:
        query: Wert für ``query``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    filters = Q(public_id__icontains=query) | Q(raw_name__icontains=query) | Q(raw_value__icontains=query) | Q(raw_unit__icontains=query) | Q(original_text__icontains=query) | Q(analyte__display_name__icontains=query) | Q(report__patient__display_name__icontains=query)
    candidates = ReviewCandidate.objects.select_related('analyte', 'report__patient').filter(filters).order_by('status', 'confidence')[:6]
    items = [search_item(candidate.public_id, candidate.analyte.display_name, f'{candidate.report.patient.display_name} · Confidence {candidate.confidence} % · {candidate.status}', 'Review', '/review', 'fact_check', patient=candidate.report.patient) for candidate in candidates]
    return result_group('review', 'Review', '/review', items)


def build_import_group(query: str) -> dict:
    """Sucht Importjobs nach Datei, Testperson, Pipeline und Fehlertext.

    Args:
        query: Wert für ``query``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    filters = Q(public_id__icontains=query) | Q(filename__icontains=query) | Q(test_person_label__icontains=query) | Q(pipeline_step__icontains=query) | Q(error_message__icontains=query) | Q(patient__display_name__icontains=query) | Q(patient__number__icontains=query)
    jobs = ImportJob.objects.select_related('patient').filter(filters).order_by('-created_at')[:6]
    items = [search_item(job.public_id, job.filename, f'{job.patient.display_name if job.patient else job.test_person_label} · {job.status} · {job.progress} %', 'Import', '/importe', 'upload_file', patient=job.patient) for job in jobs]
    return result_group('imports', 'Importe', '/importe', items)


def build_knowledge_group(query: str) -> dict:
    """Sucht Wissenseinträge nach Laborwert, Kategorie, Text und Quellen.

    Args:
        query: Wert für ``query``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    filters = Q(analyte__key__icontains=query) | Q(analyte__display_name__icontains=query) | Q(analyte__group__name__icontains=query) | Q(patient_short_text__icontains=query) | Q(patient_long_text__icontains=query) | Q(doctor_information__icontains=query) | Q(notes__icontains=query) | Q(sources__title__icontains=query) | Q(sources__reference__icontains=query)
    entries = KnowledgeEntry.objects.select_related('analyte__group').filter(filters).distinct().order_by('analyte__display_name')[:8]
    items = [search_item(f'wissen-{entry.analyte.key}', entry.analyte.display_name, f'{entry.analyte.group.name} · v{entry.version} · {entry.status}', 'Wissen', '/wissensbasis', 'menu_book') for entry in entries]
    return result_group('knowledge', 'Wissensbasis', '/wissensbasis', items)


def build_patient_report_group(query: str) -> dict:
    """Sucht Patientenberichte nach Patient, Status und Zusammenfassung.

    Args:
        query: Wert für ``query``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    filters = Q(public_id__icontains=query) | Q(patient__display_name__icontains=query) | Q(patient__number__icontains=query) | Q(total_status__icontains=query) | Q(total_text__icontains=query) | Q(summary__icontains=query)
    reports = PatientReport.objects.select_related('patient').filter(filters).order_by('-report_date')[:6]
    items = [search_item(report.public_id, f'Patientenbericht {report.report_date:%d.%m.%Y}', f'{report.patient.display_name} · {report.status} · {report.total_status}', 'Bericht', '/berichte', 'article', patient=report.patient) for report in reports]
    return result_group('reports', 'Patientenberichte', '/berichte', items)
