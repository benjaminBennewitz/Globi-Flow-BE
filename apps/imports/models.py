# apps/imports/models.py

"""Modelle für lokale Dateiimporte und Analysejobs."""

from django.db import models
from apps.core.models import TimeStampedModel
from apps.patients.models import Patient


class ImportJob(TimeStampedModel):
    """Speichert einen lokalen Importjob für PDF-Textanalyse oder OCR."""

    class Status(models.TextChoices):
        WAITING = 'wartet', 'Wartet'
        ANALYZING = 'analysiert', 'Analysiert'
        REVIEW = 'review', 'Review'
        DONE = 'abgeschlossen', 'Abgeschlossen'
        ERROR = 'fehler', 'Fehler'

    class AnalysisType(models.TextChoices):
        TEXT_LAYER = 'textschicht', 'Textschicht'
        OCR = 'ocr', 'OCR'
        DEMO = 'demo', 'Demo'

    class OcrStatus(models.TextChoices):
        NOT_REQUIRED = 'nicht_erforderlich', 'Nicht erforderlich'
        REQUIRED = 'erforderlich', 'Erforderlich'
        ACTIVE = 'aktiv', 'Aktiv'
        DONE = 'abgeschlossen', 'Abgeschlossen'
        ERROR = 'fehler', 'Fehler'

    public_id = models.CharField(max_length=64, unique=True, db_index=True)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, related_name='import_jobs', null=True, blank=True)
    source_file = models.FileField(upload_to='imports/%Y/%m/', null=True, blank=True)
    filename = models.CharField(max_length=220)
    test_person_label = models.CharField(max_length=180, blank=True)
    analysis_type = models.CharField(max_length=20, choices=AnalysisType.choices, default=AnalysisType.TEXT_LAYER, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING, db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    pipeline_step = models.CharField(max_length=160, default='Upload wartet')
    ocr_status = models.CharField(max_length=24, choices=OcrStatus.choices, default=OcrStatus.NOT_REQUIRED, db_index=True)
    recognized_values = models.PositiveSmallIntegerField(default=0)
    uncertain_values = models.PositiveSmallIntegerField(default=0)
    confidence = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', '-created_at']), models.Index(fields=['analysis_type', 'ocr_status'])]

    def __str__(self) -> str:
        return f'{self.filename} · {self.status}'


class ImportStep(TimeStampedModel):
    """Speichert einen einzelnen Pipeline-Schritt."""

    class Status(models.TextChoices):
        DONE = 'erledigt', 'Erledigt'
        ACTIVE = 'aktiv', 'Aktiv'
        WAITING = 'wartet', 'Wartet'
        ERROR = 'fehler', 'Fehler'
        SKIPPED = 'uebersprungen', 'Übersprungen'

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name='steps')
    key = models.SlugField(max_length=80)
    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    is_completed = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['sort_order', 'id']
        constraints = [models.UniqueConstraint(fields=['job', 'key'], name='unique_step_per_import_job')]


class ImportDataset(TimeStampedModel):
    """Speichert erkannte Datengruppen eines Imports."""

    class Status(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        REVIEW = 'review', 'Review'
        ERROR = 'fehler', 'Fehler'

    public_id = models.CharField(max_length=64, db_index=True)
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name='datasets')
    name = models.CharField(max_length=140)
    values_count = models.PositiveSmallIntegerField(default=0)
    review_count = models.PositiveSmallIntegerField(default=0)
    confidence = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NORMAL)

    class Meta:
        ordering = ['name']


class ImportLog(TimeStampedModel):
    """Speichert auditierbare Importereignisse."""

    public_id = models.CharField(max_length=64, db_index=True)
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name='logs')
    time_label = models.CharField(max_length=40)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=24, default='info')

    class Meta:
        ordering = ['created_at', 'id']
