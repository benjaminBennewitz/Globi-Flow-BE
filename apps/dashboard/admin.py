# apps/dashboard/admin.py

"""Admin-Registrierung für dashboard."""

from django.contrib import admin
from django.apps import apps


for model in apps.get_app_config('dashboard').get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
