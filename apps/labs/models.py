# apps/labs/models.py

"""Normalisierte Modelle für Laborbefunde und Laborwerte."""

from django.db import models
from apps.core.models import TimeStampedModel
from apps.patients.models import Patient


class LabGroup(TimeStampedModel):
    """Speichert eine fachliche Laborwertgruppe."""

    key = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self) -> str:
        return self.name


class LabAnalyte(TimeStampedModel):
    """Speichert einen stabilen Laborwert-Key."""

    key = models.SlugField(max_length=100, unique=True, db_index=True)
    display_name = models.CharField(max_length=160)
    group = models.ForeignKey(LabGroup, on_delete=models.PROTECT, related_name='analytes')
    aliases = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['group__sort_order', 'sort_order', 'display_name']
        indexes = [models.Index(fields=['group', 'is_active'])]

    def __str__(self) -> str:
        return self.display_name


class LabUnit(TimeStampedModel):
    """Speichert Einheiten unabhängig vom einzelnen Messwert."""

    code = models.CharField(max_length=40, unique=True)
    normalized_code = models.CharField(max_length=40, db_index=True)

    class Meta:
        ordering = ['code']

    def __str__(self) -> str:
        return self.code


class ReferenceRange(TimeStampedModel):
    """Speichert einen wiederverwendbaren Referenzbereich für einen Laborwert."""

    class Sex(models.TextChoices):
        FEMALE = 'weiblich', 'Weiblich'
        MALE = 'maennlich', 'Männlich'
        DIVERSE = 'divers', 'Divers'
        UNKNOWN = 'unbekannt', 'Unbekannt'
        ANY = 'alle', 'Alle'

    analyte = models.ForeignKey(LabAnalyte, on_delete=models.CASCADE, related_name='reference_ranges')
    unit = models.ForeignKey(LabUnit, on_delete=models.PROTECT, related_name='reference_ranges')
    sex = models.CharField(max_length=16, choices=Sex.choices, default=Sex.ANY)
    age_min = models.PositiveSmallIntegerField(null=True, blank=True)
    age_max = models.PositiveSmallIntegerField(null=True, blank=True)
    lower = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    upper = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    source_note = models.CharField(max_length=240, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analyte', 'unit', 'sex', 'age_min', 'age_max', 'lower', 'upper'], name='unique_reference_range')]
        indexes = [models.Index(fields=['analyte', 'unit', 'sex'])]

    def __str__(self) -> str:
        return f'{self.analyte.key} {self.lower}–{self.upper} {self.unit.code}'


class LabReport(TimeStampedModel):
    """Speichert den Befundkopf eines Laborberichts."""

    class Status(models.TextChoices):
        IMPORTED = 'importiert', 'Importiert'
        REVIEW_OPEN = 'review_offen', 'Review offen'
        RELEASED = 'freigegeben', 'Freigegeben'
        REPORT_READY = 'bericht_bereit', 'Bericht bereit'
        OCR_REVIEW = 'ocr_review', 'OCR-Review'

    public_id = models.CharField(max_length=64, unique=True, db_index=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_reports')
    name = models.CharField(max_length=220)
    report_date = models.DateField(db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.IMPORTED, db_index=True)
    source = models.CharField(max_length=40, default='demo', db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-report_date', '-created_at']
        indexes = [models.Index(fields=['patient', '-report_date']), models.Index(fields=['status', '-report_date'])]

    def __str__(self) -> str:
        return f'{self.patient.display_name} · {self.name}'


class LabValue(TimeStampedModel):
    """Speichert einen normalisierten Laborwert zu genau einem Befund."""

    class Status(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        HIGH = 'hoch', 'Hoch'
        LOW = 'niedrig', 'Niedrig'
        REVIEW = 'review', 'Review'

    class Priority(models.TextChoices):
        LOW = 'niedrig', 'Niedrig'
        MEDIUM = 'mittel', 'Mittel'
        HIGH = 'hoch', 'Hoch'

    class ReviewStatus(models.TextChoices):
        CHECKED = 'geprueft', 'Geprüft'
        REVIEW = 'review', 'Review'

    public_id = models.CharField(max_length=64, unique=True, db_index=True)
    report = models.ForeignKey(LabReport, on_delete=models.CASCADE, related_name='values')
    analyte = models.ForeignKey(LabAnalyte, on_delete=models.PROTECT, related_name='values')
    unit = models.ForeignKey(LabUnit, on_delete=models.PROTECT, related_name='values')
    reference_range = models.ForeignKey(ReferenceRange, on_delete=models.PROTECT, related_name='values')
    value = models.DecimalField(max_digits=12, decimal_places=4)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NORMAL, db_index=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.LOW, db_index=True)
    review_status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.CHECKED, db_index=True)
    confidence = models.PositiveSmallIntegerField(default=100)
    hint = models.TextField(blank=True)
    original_text = models.TextField(blank=True)

    class Meta:
        ordering = ['analyte__group__sort_order', 'analyte__sort_order', 'analyte__display_name']
        constraints = [models.UniqueConstraint(fields=['report', 'analyte'], name='unique_value_per_report_analyte')]
        indexes = [models.Index(fields=['report', 'status']), models.Index(fields=['analyte', 'status']), models.Index(fields=['review_status', 'confidence'])]

    def __str__(self) -> str:
        return f'{self.analyte.display_name}: {self.value} {self.unit.code}'


class ReviewCandidate(TimeStampedModel):
    """Speichert einen prüfpflichtigen Wert aus Parser, OCR oder manueller Eingabe."""

    class Status(models.TextChoices):
        OPEN = 'offen', 'Offen'
        CORRECTED = 'korrigiert', 'Korrigiert'
        CONFIRMED = 'bestaetigt', 'Bestätigt'
        DISCARDED = 'verworfen', 'Verworfen'
        BLOCKED = 'blockiert', 'Blockiert'

    class Source(models.TextChoices):
        PDF_TEXT = 'pdf_text', 'PDF-Text'
        OCR = 'ocr', 'OCR'
        MANUAL = 'manuell', 'Manuell'
        DEMO = 'demo', 'Demo'

    public_id = models.CharField(max_length=64, unique=True, db_index=True)
    report = models.ForeignKey(LabReport, on_delete=models.CASCADE, related_name='review_candidates')
    lab_value = models.ForeignKey(LabValue, on_delete=models.SET_NULL, related_name='review_candidates', null=True, blank=True)
    analyte = models.ForeignKey(LabAnalyte, on_delete=models.PROTECT, related_name='review_candidates')
    raw_name = models.CharField(max_length=160)
    raw_value = models.CharField(max_length=80)
    corrected_value = models.DecimalField(max_digits=12, decimal_places=4)
    raw_unit = models.CharField(max_length=40)
    corrected_unit = models.ForeignKey(LabUnit, on_delete=models.PROTECT, related_name='review_candidates')
    reference_range = models.ForeignKey(ReferenceRange, on_delete=models.PROTECT, related_name='review_candidates')
    original_text = models.TextField(blank=True)
    original_label = models.CharField(max_length=120, blank=True)
    confidence = models.PositiveSmallIntegerField(default=0, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.PDF_TEXT, db_index=True)
    comment = models.TextField(blank=True)
    parser_hints = models.JSONField(default=list, blank=True)
    checks = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['status', 'confidence', 'analyte__display_name']
        indexes = [models.Index(fields=['report', 'status']), models.Index(fields=['source', 'status'])]

    def __str__(self) -> str:
        return f'{self.analyte.display_name} · {self.status}'
