# apps/core/apps.py

"""Django-App-Konfiguration für Core."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Registriert die App Core."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'
