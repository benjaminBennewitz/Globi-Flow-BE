# apps/knowledge/apps.py

"""Django-App-Konfiguration für Wissensbasis."""

from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    """Registriert die App Wissensbasis."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.knowledge'
    verbose_name = 'Wissensbasis'
