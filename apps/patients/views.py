# apps/patients/views.py

"""API-Views für Patienten und Testpersonen."""

from rest_framework.generics import ListCreateAPIView
from apps.patients.models import Patient
from apps.patients.serializers import PatientCreateSerializer, PatientFrontendSerializer


class PatientListCreateView(ListCreateAPIView):
    """Listet Testpersonen und legt neue lokale Testpersonen an."""

    def get_queryset(self):
        """Lädt Befunde und Berichte in wenigen Queries vor."""
        return Patient.objects.prefetch_related('lab_reports__values', 'lab_reports__review_candidates', 'patient_reports').order_by('display_name')

    def get_serializer_class(self):
        """Nutzt für POST einen Eingabeserializer und für GET das Frontendformat."""
        if self.request.method == 'POST':
            return PatientCreateSerializer
        return PatientFrontendSerializer
