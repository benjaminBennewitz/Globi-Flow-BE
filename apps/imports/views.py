# apps/imports/views.py

"""API-Views für Importjobs und Review-Warteschlange."""

from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.utils import public_id
from apps.imports.async_runner import start_import_job_processing
from apps.imports.models import ImportDataset, ImportJob, ImportLog
from apps.imports.presenters import import_job_to_frontend
from apps.imports.services import create_default_steps, create_upload_job
from apps.imports.validators import validate_pdf_upload
from apps.labs.models import LabAnalyte, LabGroup, LabReport, LabUnit, LabValue, ReferenceRange, ReviewCandidate
from apps.labs.presenters import review_candidate_to_frontend
from apps.patients.models import Patient


def to_decimal(value, fallback=Decimal('0')) -> Decimal:
    """Wandelt API-Eingaben robust in Decimal um."""
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, TypeError, ValueError):
        return fallback


def import_job_queryset():
    """Lädt Importjobs mit allen Statusrelationen."""
    return ImportJob.objects.select_related('patient').prefetch_related('steps', 'datasets', 'logs')


def ensure_unit(code: str) -> LabUnit:
    """Lädt oder erstellt eine Laborwert-Einheit."""
    clean_code = str(code or '').strip() or 'ohne Einheit'
    unit, _ = LabUnit.objects.get_or_create(code=clean_code, defaults={'normalized_code': clean_code.lower()})
    return unit


def slugify_key(value: str, fallback: str = 'wert') -> str:
    """Erzeugt einen DB-stabilen Schlüssel ohne Umlaut-Dubletten."""
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'}
    result = str(value or fallback).strip().lower()
    for source, target in replacements.items():
        result = result.replace(source, target)
    result = '_'.join(''.join(char if char.isalnum() else ' ' for char in result).split())
    return result or fallback


def ensure_group(group_name: str = 'Manuelle Werte') -> LabGroup:
    """Lädt oder erstellt eine Laborgruppe ohne Unique-Konflikte über Namen."""
    safe_name = str(group_name or 'Manuelle Werte').strip() or 'Manuelle Werte'
    safe_key = slugify_key(safe_name, 'manuelle_werte')
    group = LabGroup.objects.filter(Q(key=safe_key) | Q(name__iexact=safe_name)).order_by('id').first()
    if group:
        return group
    return LabGroup.objects.create(key=safe_key, name=safe_name)


def ensure_analyte(key: str, display_name: str, group_name: str = 'Manuelle Werte') -> LabAnalyte:
    """Lädt oder erstellt einen Laborwert inklusive Gruppe."""
    safe_name = str(display_name or key or 'Manueller Laborwert').strip() or 'Manueller Laborwert'
    safe_key = slugify_key(key or safe_name, 'manueller_laborwert')
    group = ensure_group(group_name)
    analyte, _ = LabAnalyte.objects.get_or_create(key=safe_key, defaults={'display_name': safe_name, 'group': group, 'aliases': [safe_name, safe_key.replace('_', ' ')]})
    changed_fields = []
    if analyte.display_name != safe_name:
        analyte.display_name = safe_name
        changed_fields.append('display_name')
    if analyte.group_id != group.id:
        analyte.group = group
        changed_fields.append('group')
    if changed_fields:
        analyte.save(update_fields=[*changed_fields, 'updated_at'])
    return analyte


def ensure_reference(analyte: LabAnalyte, unit: LabUnit, lower: Decimal, upper: Decimal) -> ReferenceRange:
    """Lädt oder erstellt einen Referenzbereich."""
    reference, _ = ReferenceRange.objects.get_or_create(analyte=analyte, unit=unit, sex=ReferenceRange.Sex.ANY, age_min=None, age_max=None, lower=lower, upper=upper, defaults={'source_note': 'Manuell oder Review gepflegt'})
    return reference


def status_for_value(value: Decimal, lower: Decimal, upper: Decimal, confidence: int = 100) -> str:
    """Berechnet den Wertstatus anhand des Referenzbereichs."""
    if confidence < 75:
        return LabValue.Status.REVIEW
    if value < lower:
        return LabValue.Status.LOW
    if value > upper:
        return LabValue.Status.HIGH
    return LabValue.Status.NORMAL


def priority_for_status(value_status: str) -> str:
    """Leitet eine Anzeigepriorität aus dem Wertstatus ab."""
    if value_status == LabValue.Status.HIGH:
        return LabValue.Priority.HIGH
    if value_status in {LabValue.Status.LOW, LabValue.Status.REVIEW}:
        return LabValue.Priority.MEDIUM
    return LabValue.Priority.LOW


def refresh_report_review_status(report: LabReport) -> None:
    """Aktualisiert den Befundstatus nach Review-Änderungen."""
    has_open_candidates = report.review_candidates.filter(status__in=[ReviewCandidate.Status.OPEN, ReviewCandidate.Status.BLOCKED]).exists()
    has_review_values = report.values.filter(review_status=LabValue.ReviewStatus.REVIEW).exists()
    if has_open_candidates or has_review_values:
        next_status = LabReport.Status.REVIEW_OPEN
    elif report.status == LabReport.Status.RELEASED:
        next_status = LabReport.Status.RELEASED
    else:
        next_status = LabReport.Status.REPORT_READY
    if report.status != next_status:
        report.status = next_status
        report.save(update_fields=['status', 'updated_at'])


def parse_reference_range(raw_value: str) -> tuple[Decimal, Decimal]:
    """Liest einfache Referenzbereiche wie 4.0-10.0 ein."""
    clean_value = str(raw_value or '').replace('–', '-').replace(',', '.')
    parts = [part.strip() for part in clean_value.split('-', maxsplit=1)]
    if len(parts) != 2:
        return Decimal('0'), Decimal('999999')
    return to_decimal(parts[0]), to_decimal(parts[1], Decimal('999999'))


class ImportJobListView(APIView):
    """Listet Importjobs für die Statusroute."""

    def get(self, request):
        """Gibt Importjobs im Frontendformat aus."""
        jobs = import_job_queryset()[:50]
        return Response([import_job_to_frontend(job) for job in jobs])


class ImportJobDetailView(APIView):
    """Liest, aktualisiert und löscht einzelne Importjobs."""

    def get_object(self, public_id: str) -> ImportJob:
        """Lädt einen Importjob anhand der öffentlichen ID."""
        return get_object_or_404(import_job_queryset(), public_id=public_id)

    def get(self, request, public_id: str):
        """Gibt einen Importjob zurück."""
        return Response(import_job_to_frontend(self.get_object(public_id)))

    def patch(self, request, public_id: str):
        """Aktualisiert einfache Statusfelder eines Importjobs."""
        job = self.get_object(public_id)
        job.status = request.data.get('status', job.status)
        job.pipeline_step = request.data.get('pipelineSchritt', job.pipeline_step)
        if 'fortschritt' in request.data:
            job.progress = max(0, min(100, int(request.data.get('fortschritt') or 0)))
        job.error_message = request.data.get('fehlermeldung', job.error_message)
        job.save()
        return Response(import_job_to_frontend(self.get_object(public_id)))

    def delete(self, request, public_id: str):
        """Löscht einen lokalen Importjob inklusive Pipeline-Daten."""
        self.get_object(public_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UploadImportView(APIView):
    """Nimmt lokale PDF-Uploads entgegen."""

    throttle_scope = 'upload'

    def post(self, request):
        """Validiert die Datei und startet die lokale Analyse."""
        uploaded_file = request.FILES.get('file')
        if uploaded_file is None:
            raise serializers.ValidationError('Es wurde keine Datei übergeben.')
        validate_pdf_upload(uploaded_file)
        patient = None
        patient_id = request.data.get('patientId')
        if patient_id:
            patient = Patient.objects.filter(public_id=patient_id).first()
        job = create_upload_job(uploaded_file, patient=patient)
        start_import_job_processing(job.id)
        job.refresh_from_db()
        return Response(import_job_to_frontend(import_job_queryset().get(id=job.id)), status=status.HTTP_201_CREATED)


class ManualImportView(APIView):
    """Legt eine manuelle Fallback-Erfassung als Reviewjob an."""

    def post(self, request):
        """Speichert einen manuellen Laborwert als Importjob und Reviewkandidat."""
        patient = Patient.objects.filter(public_id=request.data.get('patientId')).first() or Patient.objects.order_by('id').first()
        if patient is None:
            raise serializers.ValidationError('Für die manuelle Eingabe ist zuerst eine Testperson erforderlich.')

        name = str(request.data.get('name') or request.data.get('anzeigename') or 'Manueller Laborwert').strip()
        key = str(request.data.get('key') or name.lower().replace(' ', '_')).strip()
        unit = ensure_unit(str(request.data.get('einheit') or '').strip())
        lower, upper = parse_reference_range(request.data.get('referenz'))
        result_value = to_decimal(request.data.get('ergebnis'))
        analyte = ensure_analyte(key, name)
        reference = ensure_reference(analyte, unit, lower, upper)
        report = LabReport.objects.create(public_id=public_id('befund', LabReport.objects.count() + 1), patient=patient, name='Manuelle Erfassung', report_date=timezone.localdate(), status=LabReport.Status.REVIEW_OPEN, source='manuell')
        value_status = status_for_value(result_value, lower, upper, 70)
        lab_value = LabValue.objects.create(public_id=public_id('wert', LabValue.objects.count() + 1), report=report, analyte=analyte, unit=unit, reference_range=reference, value=result_value, status=LabValue.Status.REVIEW, priority=priority_for_status(value_status), review_status=LabValue.ReviewStatus.REVIEW, confidence=70, hint='Manuell eingegeben und zur Prüfung markiert.', original_text=f'{name} {result_value} {unit.code} · Referenz {lower}-{upper}')
        ReviewCandidate.objects.create(public_id=public_id('review', ReviewCandidate.objects.count() + 1), report=report, lab_value=lab_value, analyte=analyte, raw_name=name, raw_value=str(result_value), corrected_value=result_value, raw_unit=unit.code, corrected_unit=unit, reference_range=reference, original_text=lab_value.original_text, original_label='Manuelle Eingabe', confidence=70, status=ReviewCandidate.Status.OPEN, source=ReviewCandidate.Source.MANUAL, parser_hints=['Manuelle Eingabe muss ärztlich bestätigt werden.'], checks=[{'id': 'check-manuell', 'titel': 'Manuelle Eingabe', 'beschreibung': 'Wert, Einheit und Referenzbereich prüfen.', 'status': 'pruefen'}])
        job = ImportJob.objects.create(public_id=public_id('import', ImportJob.objects.count() + 1), patient=patient, filename='manuelle-erfassung-demo.pdf', test_person_label=patient.display_name, analysis_type=ImportJob.AnalysisType.TEXT_LAYER, status=ImportJob.Status.REVIEW, progress=100, pipeline_step='Manuelle Erfassung für Review vorbereitet', ocr_status=ImportJob.OcrStatus.NOT_REQUIRED, recognized_values=1, uncertain_values=1, confidence=70)
        create_default_steps(job)
        job.steps.update(status='erledigt', is_completed=True)
        ImportDataset.objects.create(public_id=f'dataset-{job.public_id}-manuell', job=job, name=name, values_count=1, review_count=1, confidence=70, status=ImportDataset.Status.REVIEW)
        ImportLog.objects.create(public_id=f'log-{job.public_id}-1', job=job, time_label=timezone.localtime().strftime('%H:%M'), title='Manuelle Eingabe erfasst', description=lab_value.original_text, status=ImportJob.Status.REVIEW)
        return Response(import_job_to_frontend(import_job_queryset().get(id=job.id)), status=status.HTTP_201_CREATED)


class DemoImportView(APIView):
    """Startet einen Demo-Import auf Basis vorhandener Seed-Daten."""

    def post(self, request):
        """Gibt den neuesten Demo-Importjob zurück."""
        job = import_job_queryset().order_by('-created_at').first()
        if job is None:
            return Response({'detail': 'Keine Demo-Daten vorhanden. Bitte seed_demo_data ausführen.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(import_job_to_frontend(job))


class ReviewQueueView(APIView):
    """Liefert Review-Kandidaten."""

    def get(self, request):
        """Gibt die Reviewansicht zurück."""
        candidates = ReviewCandidate.objects.select_related('report__patient', 'analyte__group', 'corrected_unit', 'reference_range').all()
        return Response({'kandidaten': [review_candidate_to_frontend(candidate) for candidate in candidates]})


class ReviewCandidateDetailView(APIView):
    """Aktualisiert einen einzelnen Review-Kandidaten."""

    @transaction.atomic
    def patch(self, request, public_id: str):
        """Speichert Korrektur, Einheit, Kommentar oder Status."""
        candidate = get_object_or_404(ReviewCandidate.objects.select_related('lab_value', 'report', 'analyte__group', 'corrected_unit', 'reference_range'), public_id=public_id)
        analyte = candidate.analyte
        if 'laborwertKey' in request.data or 'anzeigename' in request.data:
            analyte = ensure_analyte(request.data.get('laborwertKey', analyte.key), request.data.get('anzeigename', analyte.display_name), analyte.group.name)
            candidate.analyte = analyte
        candidate.status = request.data.get('status', candidate.status)
        candidate.comment = request.data.get('kommentar', candidate.comment)
        if 'erkannterName' in request.data:
            candidate.raw_name = request.data['erkannterName']
        if 'erkannterWert' in request.data:
            candidate.raw_value = request.data['erkannterWert']
        if 'korrigierterWert' in request.data:
            candidate.corrected_value = to_decimal(request.data['korrigierterWert'], candidate.corrected_value)
        if 'korrigierteEinheit' in request.data:
            candidate.corrected_unit = ensure_unit(request.data['korrigierteEinheit'])
        lower = to_decimal(request.data.get('referenzMin'), candidate.reference_range.lower)
        upper = to_decimal(request.data.get('referenzMax'), candidate.reference_range.upper)
        candidate.reference_range = ensure_reference(analyte, candidate.corrected_unit, lower, upper)
        if candidate.lab_value and candidate.status in {ReviewCandidate.Status.CONFIRMED, ReviewCandidate.Status.CORRECTED}:
            value_status = status_for_value(candidate.corrected_value, lower, upper, 100)
            candidate.lab_value.analyte = analyte
            candidate.lab_value.value = candidate.corrected_value
            candidate.lab_value.unit = candidate.corrected_unit
            candidate.lab_value.reference_range = candidate.reference_range
            candidate.lab_value.review_status = LabValue.ReviewStatus.CHECKED
            candidate.lab_value.status = value_status
            candidate.lab_value.priority = priority_for_status(value_status)
            candidate.lab_value.save()
        if candidate.lab_value and candidate.status == ReviewCandidate.Status.DISCARDED:
            candidate.lab_value.review_status = LabValue.ReviewStatus.CHECKED
            candidate.lab_value.status = LabValue.Status.NORMAL
            candidate.lab_value.save(update_fields=['review_status', 'status', 'updated_at'])
        candidate.save()
        refresh_report_review_status(candidate.report)
        candidate.refresh_from_db()
        return Response(review_candidate_to_frontend(candidate))


class ReviewCandidateBulkUpdateView(APIView):
    """Aktualisiert mehrere Review-Kandidaten in einem API-Aufruf."""

    @transaction.atomic
    def post(self, request):
        """Setzt Statuswerte für sichere oder geprüfte Kandidaten."""
        ids = request.data.get('ids', [])
        target_status = request.data.get('status', ReviewCandidate.Status.CONFIRMED)
        candidates = ReviewCandidate.objects.select_related('lab_value', 'analyte__group', 'corrected_unit', 'reference_range', 'report__patient').filter(public_id__in=ids)
        result = []
        touched_reports = set()
        for candidate in candidates:
            candidate.status = target_status
            candidate.save(update_fields=['status', 'updated_at'])
            if candidate.lab_value and target_status in {ReviewCandidate.Status.CONFIRMED, ReviewCandidate.Status.CORRECTED}:
                candidate.lab_value.review_status = LabValue.ReviewStatus.CHECKED
                candidate.lab_value.status = status_for_value(candidate.lab_value.value, candidate.lab_value.reference_range.lower, candidate.lab_value.reference_range.upper, 100)
                candidate.lab_value.save(update_fields=['review_status', 'status', 'updated_at'])
            touched_reports.add(candidate.report_id)
            result.append(review_candidate_to_frontend(candidate))
        for report in LabReport.objects.filter(id__in=touched_reports):
            refresh_report_review_status(report)
        return Response({'kandidaten': result})
