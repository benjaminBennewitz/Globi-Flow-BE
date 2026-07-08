# apps/patients/urls.py

"""URLs für Patienten."""

from django.urls import path
from apps.patients.views import PatientDetailView, PatientListCreateView

urlpatterns = [
    path('patients/', PatientListCreateView.as_view(), name='patients'),
    path('patients/<str:public_id>/', PatientDetailView.as_view(), name='patient-detail'),
]
