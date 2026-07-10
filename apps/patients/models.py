# apps/patients/models.py

"""Patienten- und Testpersonenmodelle."""

from django.db import models
from apps.core.models import TimeStampedModel


class Patient(TimeStampedModel):
    """Speichert eine fiktive Testperson oder später einen lokalen Patientenstammdatensatz."""

    class Sex(models.TextChoices):
        """Im Testdatensatz geführte Geschlechtsangabe einer Person."""

        FEMALE = 'weiblich', 'Weiblich'
        MALE = 'maennlich', 'Männlich'
        DIVERSE = 'divers', 'Divers'
        UNKNOWN = 'unbekannt', 'Unbekannt'

    class Source(models.TextChoices):
        """Quelle, über die die Testperson angelegt wurde."""

        DEMO = 'demo', 'Demo'
        HISTORY = 'verlauf', 'Verlauf'
        OCR = 'ocr', 'OCR'
        MANUAL = 'manuell', 'Manuell'

    class Status(models.TextChoices):
        """Aktueller fachlicher Arbeitsstatus der Testperson."""

        ACTIVE = 'aktiv', 'Aktiv'
        REVIEW = 'review', 'Review'
        IMPORT = 'import', 'Import'
        REPORT = 'bericht', 'Bericht'
        EMPTY = 'leer', 'Leer'

    public_id = models.CharField(max_length=64, unique=True, db_index=True)
    number = models.CharField(max_length=32, unique=True, db_index=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    display_name = models.CharField(max_length=180, db_index=True)
    birth_date = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=16, choices=Sex.choices, default=Sex.UNKNOWN)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    lifestyle = models.CharField(max_length=240, blank=True)
    non_smoker = models.BooleanField(default=False)
    drinks_alcohol = models.BooleanField(default=False)
    uses_drugs = models.BooleanField(default=False)
    context = models.CharField(max_length=240, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.EMPTY, db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['display_name']
        indexes = [models.Index(fields=['source', 'status']), models.Index(fields=['last_name', 'first_name'])]

    def __str__(self) -> str:
        return f'{self.display_name} ({self.number})'
