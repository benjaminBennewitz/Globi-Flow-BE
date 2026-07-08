# apps/patients/urls.py

"""URLs für Patienten."""

from django.urls import path
from apps.patients.views import PatientListCreateView

urlpatterns = [path('patients/', PatientListCreateView.as_view(), name='patients')]
