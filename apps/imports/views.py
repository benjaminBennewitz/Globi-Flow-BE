# apps/imports/views.py

"""API-Views für Importjobs und Review-Warteschlange."""

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.imports.models import ImportJob
from apps.imports.presenters import import_job_to_frontend
from apps.imports.services import create_upload_job, process_import_job
from apps.imports.tasks import process_import_job_task
from apps.imports.validators import validate_pdf_upload
from apps.labs.models import ReviewCandidate
from apps.labs.presenters import review_candidate_to_frontend
from apps.patients.models import Patient


class ImportJobListView(APIView):
    """Listet Importjobs für die Statusroute."""

    def get(self, request):
        """Gibt Importjobs im Frontendformat aus."""
        jobs = ImportJob.objects.select_related('patient').prefetch_related('steps', 'datasets', 'logs')[:50]
        return Response([import_job_to_frontend(job) for job in jobs])


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
        if settings.GLOBI_USE_CELERY:
            process_import_job_task.delay(job.id)
        else:
            process_import_job(job.id)
            job.refresh_from_db()
        return Response(import_job_to_frontend(ImportJob.objects.prefetch_related('steps', 'datasets', 'logs').get(id=job.id)), status=status.HTTP_201_CREATED)


class DemoImportView(APIView):
    """Startet einen Demo-Import auf Basis vorhandener Seed-Daten."""

    def post(self, request):
        """Gibt den neuesten Demo-Importjob zurück."""
        job = ImportJob.objects.select_related('patient').prefetch_related('steps', 'datasets', 'logs').order_by('-created_at').first()
        if job is None:
            return Response({'detail': 'Keine Demo-Daten vorhanden. Bitte seed_demo_data ausführen.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(import_job_to_frontend(job))


class ReviewQueueView(APIView):
    """Liefert und aktualisiert Review-Kandidaten."""

    def get(self, request):
        """Gibt die Reviewansicht zurück."""
        candidates = ReviewCandidate.objects.select_related('report__patient', 'analyte__group', 'corrected_unit', 'reference_range').all()
        return Response({'kandidaten': [review_candidate_to_frontend(candidate) for candidate in candidates]})


class ReviewCandidateDetailView(APIView):
    """Aktualisiert einen einzelnen Review-Kandidaten."""

    def patch(self, request, public_id: str):
        """Speichert Korrektur, Einheit, Kommentar oder Status."""
        candidate = ReviewCandidate.objects.select_related('lab_value', 'corrected_unit', 'reference_range').get(public_id=public_id)
        candidate.status = request.data.get('status', candidate.status)
        candidate.comment = request.data.get('kommentar', candidate.comment)
        if 'korrigierterWert' in request.data:
            candidate.corrected_value = request.data['korrigierterWert']
        if candidate.lab_value and candidate.status in {ReviewCandidate.Status.CONFIRMED, ReviewCandidate.Status.CORRECTED}:
            candidate.lab_value.value = candidate.corrected_value
            candidate.lab_value.review_status = 'geprueft'
            candidate.lab_value.status = 'normal'
            candidate.lab_value.save(update_fields=['value', 'review_status', 'status', 'updated_at'])
        candidate.save()
        candidate.refresh_from_db()
        return Response(review_candidate_to_frontend(candidate))
