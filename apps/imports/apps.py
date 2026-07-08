# apps/imports/apps.py

"""Django-App-Konfiguration für Importe."""

from django.apps import AppConfig


class ImportsConfig(AppConfig):
    """Registriert die App Importe."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.imports'
    verbose_name = 'Importe'
