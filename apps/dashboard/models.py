# apps/dashboard/models.py

"""Optionale aggregierte Dashboard-Inhalte aus Seeds oder späterem ETL."""

from django.db import models
from apps.core.models import TimeStampedModel


class DashboardHealthMonth(TimeStampedModel):
    """Speichert aggregierte Monatswerte für die Übersichtsroute."""

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=40)
    normal_count = models.PositiveSmallIntegerField(default=0)
    abnormal_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['year', 'month']
        constraints = [models.UniqueConstraint(fields=['year', 'month'], name='unique_dashboard_health_month')]


class DashboardNotice(TimeStampedModel):
    """Speichert dringende Hinweise für die Arztübersicht."""

    public_id = models.CharField(max_length=80, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    since = models.CharField(max_length=80)
    status = models.CharField(max_length=20, default='info')

    class Meta:
        ordering = ['status', 'title']


class DashboardActivity(TimeStampedModel):
    """Speichert letzte Aktivitäten für die Übersicht."""

    public_id = models.CharField(max_length=80, db_index=True)
    time_label = models.CharField(max_length=80)
    day_offset = models.SmallIntegerField(default=0)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, default='info')

    class Meta:
        ordering = ['day_offset', '-created_at']
