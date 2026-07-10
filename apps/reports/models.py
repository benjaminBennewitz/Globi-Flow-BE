# apps/reports/models.py

"""Modelle für kontrollierte Patientenberichte."""

from django.db import models
from apps.core.models import TimeStampedModel
from apps.labs.models import LabReport
from apps.patients.models import Patient


class PatientReport(TimeStampedModel):
    """Speichert eine Berichtsversion für einen Patienten."""

    class Status(models.TextChoices):
        """Freigabe- und Erstellungszustand eines Patientenberichts."""

        DRAFT = 'entwurf', 'Entwurf'
        READY = 'bereit', 'Bereit'
        RELEASED = 'freigegeben', 'Freigegeben'

    public_id = models.CharField(max_length=80, unique=True, db_index=True)
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='patient_reports')
    lab_report = models.ForeignKey(
        LabReport, on_delete=models.CASCADE, related_name='patient_reports', null=True, blank=True)
    report_date = models.DateField()
    version = models.CharField(max_length=20, default='1.0')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    total_status = models.CharField(max_length=240)
    total_text = models.TextField()
    summary = models.TextField(blank=True)
    checked_values = models.PositiveSmallIntegerField(default=0)
    normal_values = models.PositiveSmallIntegerField(default=0)
    abnormal_values = models.PositiveSmallIntegerField(default=0)
    review_values = models.PositiveSmallIntegerField(default=0)
    disclaimer = models.TextField()

    class Meta:
        ordering = ['-report_date', '-created_at']
        indexes = [models.Index(fields=['patient', '-report_date']),
                   models.Index(fields=['status', '-report_date'])]


class ReportSection(TimeStampedModel):
    """Speichert einen verständlichen Berichtsabschnitt."""

    report = models.ForeignKey(
        PatientReport, on_delete=models.CASCADE, related_name='sections')
    key = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)
    text = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['sort_order', 'id']


class ReportQuestion(TimeStampedModel):
    """Speichert eine Frage für das Arztgespräch."""

    public_id = models.CharField(max_length=80, db_index=True)
    report = models.ForeignKey(
        PatientReport, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField()
    area = models.CharField(max_length=120, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['sort_order', 'id']


class ReportRecommendation(TimeStampedModel):
    """Speichert eine Empfehlung oder einen Hinweis im Patientenbericht."""

    class Priority(models.TextChoices):
        """Priorität einer allgemeinen Berichtsempfehlung."""

        NORMAL = 'normal', 'Normal'
        NOTICE = 'beachten', 'Beachten'
        IMPORTANT = 'wichtig', 'Wichtig'

    public_id = models.CharField(max_length=80, db_index=True)
    report = models.ForeignKey(
        PatientReport, on_delete=models.CASCADE, related_name='recommendations')
    title = models.CharField(max_length=200)
    text = models.TextField()
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['sort_order', 'id']


class ReportSource(TimeStampedModel):
    """Speichert Quellenangaben für den Patientenbericht."""

    public_id = models.CharField(max_length=80, db_index=True)
    report = models.ForeignKey(
        PatientReport, on_delete=models.CASCADE, related_name='sources')
    area = models.CharField(max_length=120)
    title = models.CharField(max_length=240)
    source_date = models.CharField(max_length=80)

    class Meta:
        ordering = ['area', 'title']
