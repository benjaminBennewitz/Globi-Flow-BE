# apps/imports/tasks.py

"""Celery-Tasks für lokale Importanalyse."""

from config.celery import app
from apps.imports.services import process_import_job


@app.task(bind=True, name='imports.process_import_job', autoretry_for=(OSError, TimeoutError), retry_backoff=True, retry_backoff_max=300, retry_jitter=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_import_job_task(self, job_id: int) -> None:
    """Verarbeitet einen Importjob in einem lokalen Worker."""
    process_import_job(job_id)
