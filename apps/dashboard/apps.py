# apps/dashboard/apps.py

"""Django-App-Konfiguration für Dashboard."""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Registriert die App Dashboard."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dashboard'
    verbose_name = 'Dashboard'
