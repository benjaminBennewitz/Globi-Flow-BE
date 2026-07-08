# apps/reports/apps.py

"""Django-App-Konfiguration für Berichte."""

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """Registriert die App Berichte."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reports'
    verbose_name = 'Berichte'
