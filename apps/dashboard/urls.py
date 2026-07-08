# apps/dashboard/urls.py

"""URLs für aggregierte ViewModels."""

from django.urls import path
from apps.dashboard.views import DashboardView, EvaluationAliasView, OverviewView

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('overview/', OverviewView.as_view(), name='overview'),
    path('auswertung/', EvaluationAliasView.as_view(), name='auswertung-alias'),
]
