# apps/knowledge/models.py

"""Kontrollierte Wissensinhalte für Laborwerte und Patientenberichte."""

from django.db import models
from apps.core.models import TimeStampedModel
from apps.labs.models import LabAnalyte


class KnowledgeEntry(TimeStampedModel):
    """Speichert einen versionierten Erklärungstext zu einem Laborwert."""

    class Status(models.TextChoices):
        """Redaktioneller Freigabestatus eines Wissenseintrags."""

        DRAFT = 'entwurf', 'Entwurf'
        REVIEW = 'pruefung', 'Prüfung'
        RELEASED = 'freigegeben', 'Freigegeben'

    analyte = models.OneToOneField(LabAnalyte, on_delete=models.CASCADE, related_name='knowledge_entry')
    patient_short_text = models.TextField(blank=True)
    patient_long_text = models.TextField(blank=True)
    doctor_information = models.TextField(blank=True)
    causes_low = models.TextField(blank=True)
    causes_high = models.TextField(blank=True)
    influencing_factors = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    disclaimer = models.TextField(blank=True)
    version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    changed_by = models.CharField(max_length=120, default='Admin')
    changed_at_label = models.CharField(max_length=40, blank=True)
    chart_color = models.CharField(max_length=16, default='#0f5297')

    class Meta:
        ordering = ['analyte__group__name', 'analyte__display_name']
        indexes = [models.Index(fields=['status', 'version'])]

    def __str__(self) -> str:
        return self.analyte.display_name


class KnowledgeSource(TimeStampedModel):
    """Speichert Quellen zu einem Wissenseintrag."""

    class SourceType(models.TextChoices):
        """Art der fachlichen Quelle eines Wissenseintrags."""

        GUIDELINE = 'leitlinie', 'Leitlinie'
        LAB_LEXICON = 'laborlexikon', 'Laborlexikon'
        LITERATURE = 'fachliteratur', 'Fachliteratur'
        INTERNAL = 'intern', 'Intern'
        DEMO = 'demo', 'Demo'

    public_id = models.CharField(max_length=80, db_index=True)
    entry = models.ForeignKey(KnowledgeEntry, on_delete=models.CASCADE, related_name='sources')
    title = models.CharField(max_length=240)
    source_type = models.CharField(max_length=24, choices=SourceType.choices, default=SourceType.DEMO)
    source_date = models.CharField(max_length=80, blank=True)
    reference = models.CharField(max_length=500, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['title']


class KnowledgeVersion(TimeStampedModel):
    """Speichert die Änderungshistorie eines Wissenseintrags."""

    entry = models.ForeignKey(KnowledgeEntry, on_delete=models.CASCADE, related_name='versions')
    version = models.PositiveSmallIntegerField()
    date_label = models.CharField(max_length=40)
    changed_by = models.CharField(max_length=120)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-version', '-created_at']
        constraints = [models.UniqueConstraint(fields=['entry', 'version'], name='unique_knowledge_entry_version')]
