# apps/knowledge/admin.py

"""Admin-Registrierung für knowledge."""

from django.contrib import admin
from django.apps import apps


for model in apps.get_app_config('knowledge').get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
