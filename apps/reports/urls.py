# apps/reports/urls.py

"""URLs für Berichte."""

from django.urls import path
from apps.reports.views import PatientReportPreviewView, ReportPreviewView, ReportTranslationView

urlpatterns = [
    path('reports/', ReportPreviewView.as_view(), name='reports-root'),
    path('reports/preview/', ReportPreviewView.as_view(), name='report-preview'),
    path('reports/patient-preview/', PatientReportPreviewView.as_view(),
         name='patient-report-preview'),
    path('reports/translate/', ReportTranslationView.as_view(),
         name='report-translate'),
]
