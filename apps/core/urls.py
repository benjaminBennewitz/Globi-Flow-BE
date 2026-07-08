# apps/core/urls.py

"""URLs für allgemeine API-Funktionen."""

from django.urls import path
from apps.core.views import HealthView

urlpatterns = [path('health/', HealthView.as_view(), name='health')]
