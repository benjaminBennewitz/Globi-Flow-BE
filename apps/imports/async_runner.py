# apps/imports/async_runner.py

"""Startet Importjobs lokal im Hintergrund oder über Celery."""

from threading import Thread
from django.conf import settings
from django.db import close_old_connections
from apps.imports.services import process_import_job
from apps.imports.tasks import process_import_job_task


def start_import_job_processing(job_id: int) -> str:
    """Übergibt einen vorbereiteten Importjob an den Celery-Worker.

    Args:
        job_id: Primärschlüssel des zu verarbeitenden Importjobs.

    Raises:
        RuntimeError: Wenn Broker oder Result-Backend nicht erreichbar oder
            nicht korrekt authentifiziert sind.

    Side Effects:
        Erstellt eine asynchrone Aufgabe in der Queue ``globi_imports``.
    """
    if getattr(settings, "GLOBI_USE_CELERY", False):
        process_import_job_task.delay(job_id)
        return "celery"

    thread = Thread(target=run_local_import_job, args=(job_id,), name=f"globi-import-{job_id}", daemon=True)
    thread.start()
    return "local_thread"


def run_local_import_job(job_id: int) -> None:
    """Verarbeitet einen Importjob synchron als lokalen Entwicklungsfallback.

    Args:
        job_id: Primärschlüssel des zu verarbeitenden Importjobs.

    Side Effects:
        Führt die vollständige Importpipeline im aktuellen Prozess aus. Dieser
        Weg ist nur für lokale Entwicklung und Tests vorgesehen.
    """
    close_old_connections()
    try:
        process_import_job(job_id)
    finally:
        close_old_connections()
