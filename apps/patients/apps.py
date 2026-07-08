# apps/patients/apps.py

"""Django-App-Konfiguration für Patienten."""

from django.apps import AppConfig


class PatientsConfig(AppConfig):
    """Registriert die App Patienten."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.patients'
    verbose_name = 'Patienten'
