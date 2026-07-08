# apps/patients/views.py

"""API-Views für Patienten und Testpersonen."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.patients.models import Patient
from apps.patients.serializers import PatientFrontendSerializer, PatientInputSerializer


def patient_queryset():
    """Lädt Patienten inklusive Befunden und Berichten performant vor."""
    return Patient.objects.prefetch_related('lab_reports__values', 'lab_reports__review_candidates', 'patient_reports').order_by('display_name')


class PatientListCreateView(ListCreateAPIView):
    """Listet Testpersonen und legt neue lokale Testpersonen an."""

    def get_queryset(self):
        """Lädt Befunde und Berichte in wenigen Queries vor."""
        return patient_queryset()

    def get_serializer_class(self):
        """Nutzt für POST einen Eingabeserializer und für GET das Frontendformat."""
        if self.request.method == 'POST':
            return PatientInputSerializer
        return PatientFrontendSerializer

    def create(self, request, *args, **kwargs):
        """Gibt nach dem Speichern direkt das Frontendformat zurück."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        output = PatientFrontendSerializer(patient_queryset().get(id=patient.id))
        return Response(output.data, status=status.HTTP_201_CREATED)


class PatientDetailView(APIView):
    """Liest, aktualisiert und löscht einzelne Testpersonen."""

    def get_object(self, public_id: str) -> Patient:
        """Lädt eine Testperson anhand der öffentlichen ID."""
        return get_object_or_404(patient_queryset(), public_id=public_id)

    def get(self, request, public_id: str):
        """Gibt eine einzelne Testperson zurück."""
        return Response(PatientFrontendSerializer(self.get_object(public_id)).data)

    def patch(self, request, public_id: str):
        """Aktualisiert Stammdaten einer Testperson."""
        patient = self.get_object(public_id)
        serializer = PatientInputSerializer(patient, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        return Response(PatientFrontendSerializer(patient_queryset().get(id=patient.id)).data)

    def delete(self, request, public_id: str):
        """Löscht eine lokale Testperson mit ihren abhängigen Befunden."""
        self.get_object(public_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
