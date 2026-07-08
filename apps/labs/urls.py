# apps/labs/urls.py

"""URLs für Laborbefunde."""

from django.urls import path
from apps.labs.views import EvaluationView, LabReportReleaseView

urlpatterns = [
    path('evaluation/', EvaluationView.as_view(), name='evaluation'),
    path('lab-reports/release/', LabReportReleaseView.as_view(), name='lab-report-release-current'),
    path('lab-reports/<str:public_id>/release/', LabReportReleaseView.as_view(), name='lab-report-release'),
]
