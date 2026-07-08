# apps/core/models.py

"""Gemeinsame abstrakte Basismodelle."""

from django.db import models


class TimeStampedModel(models.Model):
    """Ergänzt Erstellungs- und Änderungszeitpunkt für auditierbare Datensätze."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
