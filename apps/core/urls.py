# apps/core/urls.py

"""URLs für allgemeine API-Funktionen."""

from django.urls import path
from apps.core.views import DemoDataResetView, GlobalSearchView, HealthView

urlpatterns = [path('health/', HealthView.as_view(), name='health'), path('demo-data/reset/', DemoDataResetView.as_view(), name='demo-data-reset'), path('search/', GlobalSearchView.as_view(), name='global-search')]
