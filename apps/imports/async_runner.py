# apps/imports/async_runner.py

"""Startet Importjobs lokal im Hintergrund oder über Celery."""

from threading import Thread
from django.conf import settings
from django.db import close_old_connections
from apps.imports.services import process_import_job
from apps.imports.tasks import process_import_job_task


def start_import_job_processing(job_id: int) -> str:
    """Startet einen Importjob ohne blockierenden Upload-Request."""
    if getattr(settings, "GLOBI_USE_CELERY", False):
        process_import_job_task.delay(job_id)
        return "celery"

    thread = Thread(target=run_local_import_job, args=(job_id,), name=f"globi-import-{job_id}", daemon=True)
    thread.start()
    return "local_thread"


def run_local_import_job(job_id: int) -> None:
    """Verarbeitet einen Importjob in einem separaten lokalen Thread."""
    close_old_connections()
    try:
        process_import_job(job_id)
    finally:
        close_old_connections()
