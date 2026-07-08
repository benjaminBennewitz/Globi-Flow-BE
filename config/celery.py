# config/celery.py

"""Celery-Konfiguration für optionale lokale Hintergrundjobs."""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('globi_flow')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
