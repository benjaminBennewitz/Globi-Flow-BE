# apps/labs/apps.py

"""Django-App-Konfiguration für Laborwerte."""

from django.apps import AppConfig


class LabsConfig(AppConfig):
    """Registriert die App Laborwerte."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.labs'
    verbose_name = 'Laborwerte'
