# apps/imports/presenters.py

"""Präsentationsfunktionen für Importjobs."""

from apps.core.utils import format_datetime
from apps.imports.models import ImportJob


def import_job_to_frontend(job: ImportJob) -> dict:
    """Gibt einen Importjob im Angular-Format aus."""
    return {
        'id': job.public_id,
        'dateiname': job.filename,
        'testperson': job.patient.display_name if job.patient else job.test_person_label,
        'analyseArt': job.analysis_type,
        'status': job.status,
        'fortschritt': job.progress,
        'pipelineSchritt': job.pipeline_step,
        'ocrStatus': job.ocr_status,
        'erkannteWerte': job.recognized_values,
        'unsichereWerte': job.uncertain_values,
        'confidence': job.confidence,
        'erstelltAm': format_datetime(job.created_at),
        'aktualisiertAm': format_datetime(job.updated_at),
        'fehlermeldung': job.error_message or None,
        'schritte': [
            {'key': step.key, 'name': step.name, 'beschreibung': step.description, 'status': step.status, 'abgeschlossen': step.is_completed}
            for step in job.steps.all()
        ],
        'datasets': [
            {'id': dataset.public_id, 'name': dataset.name, 'werte': dataset.values_count, 'review': dataset.review_count, 'confidence': dataset.confidence, 'status': dataset.status}
            for dataset in job.datasets.all()
        ],
        'logEintraege': [
            {'id': log.public_id, 'zeitpunkt': log.time_label, 'titel': log.title, 'beschreibung': log.description, 'status': log.status}
            for log in job.logs.all()
        ],
    }
