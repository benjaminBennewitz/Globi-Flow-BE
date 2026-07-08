# apps/imports/tasks.py

"""Celery-Tasks für lokale Importanalyse."""

from config.celery import app
from apps.imports.services import process_import_job


@app.task(name='imports.process_import_job')
def process_import_job_task(job_id: int) -> None:
    """Verarbeitet einen Importjob in einem lokalen Worker."""
    process_import_job(job_id)
