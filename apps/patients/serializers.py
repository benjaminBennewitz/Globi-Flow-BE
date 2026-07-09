# apps/patients/serializers.py

"""Serializer für Testpersonen und Patienten."""

from datetime import datetime
from django.db.models import Count, Q
from rest_framework import serializers
from apps.core.utils import decimal_to_number, format_date, public_id
from apps.imports.models import ImportJob
from apps.labs.models import LabReport, LabValue, ReviewCandidate
from apps.patients.models import Patient
from apps.reports.models import PatientReport


OPEN_REVIEW_STATUSES = [ReviewCandidate.Status.OPEN, ReviewCandidate.Status.BLOCKED]


def open_review_count(report: LabReport) -> int:
    """Zählt offene oder blockierende Reviewarbeit eines Befunds."""
    candidate_count = report.review_candidates.filter(status__in=OPEN_REVIEW_STATUSES).count()
    review_value_count = report.values.filter(Q(review_status=LabValue.ReviewStatus.REVIEW) | Q(status=LabValue.Status.REVIEW)).count()
    return candidate_count + review_value_count


def report_status(report: LabReport) -> str:
    """Berechnet den sichtbaren Befundstatus aus echten Review- und Berichtsdaten."""
    if open_review_count(report) > 0:
        return LabReport.Status.REVIEW_OPEN
    if report.status == LabReport.Status.RELEASED:
        return LabReport.Status.RELEASED
    if PatientReport.objects.filter(lab_report=report, status__in=[PatientReport.Status.READY, PatientReport.Status.RELEASED]).exists():
        return LabReport.Status.REPORT_READY
    return report.status


def patient_status(patient: Patient, reports: list[LabReport], open_reviews: int) -> str:
    """Leitet den Patientenstatus aus aktuellen Befunden, Reviews und Importen ab."""
    if ImportJob.objects.filter(patient=patient, status__in=[ImportJob.Status.WAITING, ImportJob.Status.ANALYZING]).exists():
        return Patient.Status.IMPORT
    if open_reviews > 0:
        return Patient.Status.REVIEW
    if PatientReport.objects.filter(patient=patient, status=PatientReport.Status.RELEASED).exists():
        return Patient.Status.REPORT
    if reports:
        return Patient.Status.ACTIVE
    return Patient.Status.EMPTY


class PatientInputSerializer(serializers.Serializer):
    """Validiert Testpersonen aus der Angular-App für Create und Update."""

    vorname = serializers.CharField(max_length=80, allow_blank=True, required=False)
    nachname = serializers.CharField(max_length=80, allow_blank=True, required=False)
    nummer = serializers.CharField(max_length=32, allow_blank=True, required=False)
    geburtsdatum = serializers.CharField(max_length=10, allow_blank=True, required=False)
    geschlecht = serializers.ChoiceField(choices=Patient.Sex.choices, default=Patient.Sex.UNKNOWN, required=False)
    gewichtKg = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    groesseCm = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=260)
    lebensstil = serializers.CharField(max_length=240, allow_blank=True, required=False)
    nichtrauchen = serializers.BooleanField(required=False, default=False)
    alkohol = serializers.BooleanField(required=False, default=False)
    drogen = serializers.BooleanField(required=False, default=False)
    notiz = serializers.CharField(allow_blank=True, required=False)
    kontext = serializers.CharField(max_length=240, allow_blank=True, required=False)
    status = serializers.ChoiceField(choices=Patient.Status.choices, required=False)

    def validate_geburtsdatum(self, value):
        """Akzeptiert ISO- und deutsches Datumsformat aus der Oberfläche."""
        datum = str(value or '').strip()

        if not datum:
            return None

        for formatierung in ('%Y-%m-%d', '%d.%m.%Y'):
            try:
                return datetime.strptime(datum, formatierung).date()
            except ValueError:
                continue

        raise serializers.ValidationError('Das Geburtsdatum muss als JJJJ-MM-TT oder TT.MM.JJJJ angegeben werden.')

    def validate_nummer(self, value):
        """Prüft eindeutige Testpersonen-Nummern für Create und Update."""
        number = value.strip()
        if not number:
            return number
        queryset = Patient.objects.filter(number=number)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError('Diese Testpersonen-ID ist bereits vergeben.')
        return number

    def create(self, validated_data):
        """Erstellt eine neue lokale Testperson."""
        next_number = Patient.objects.count() + 1
        first_name = validated_data.get('vorname', '').strip()
        last_name = validated_data.get('nachname', '').strip()
        display_name = f'{first_name} {last_name}'.strip() or 'Neue Testperson'
        number = validated_data.get('nummer', '').strip() or f'TP-2026-{next_number:03d}'
        patient = Patient.objects.create(
            public_id=public_id('patient', next_number),
            number=number,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            birth_date=validated_data.get('geburtsdatum'),
            sex=validated_data.get('geschlecht', Patient.Sex.UNKNOWN),
            weight_kg=validated_data.get('gewichtKg'),
            height_cm=validated_data.get('groesseCm'),
            lifestyle=validated_data.get('lebensstil', '').strip() or 'nicht angegeben',
            non_smoker=validated_data.get('nichtrauchen', False),
            drinks_alcohol=validated_data.get('alkohol', False),
            uses_drugs=validated_data.get('drogen', False),
            context=validated_data.get('kontext', '').strip() or 'lokal angelegt',
            source=Patient.Source.MANUAL,
            status=validated_data.get('status', Patient.Status.EMPTY),
            note=validated_data.get('notiz', '').strip(),
        )
        return patient

    def update(self, instance, validated_data):
        """Aktualisiert eine lokale Testperson ohne Befunddaten zu verändern."""
        first_name = validated_data.get('vorname', instance.first_name).strip()
        last_name = validated_data.get('nachname', instance.last_name).strip()
        instance.first_name = first_name
        instance.last_name = last_name
        instance.display_name = f'{first_name} {last_name}'.strip() or instance.display_name or 'Neue Testperson'
        instance.number = validated_data.get('nummer', instance.number).strip() or instance.number
        if 'geburtsdatum' in validated_data:
            instance.birth_date = validated_data.get('geburtsdatum')
        instance.sex = validated_data.get('geschlecht', instance.sex)
        if 'gewichtKg' in validated_data:
            instance.weight_kg = validated_data.get('gewichtKg')
        if 'groesseCm' in validated_data:
            instance.height_cm = validated_data.get('groesseCm')
        instance.lifestyle = validated_data.get('lebensstil', instance.lifestyle).strip() or 'nicht angegeben'
        instance.non_smoker = validated_data.get('nichtrauchen', instance.non_smoker)
        instance.drinks_alcohol = validated_data.get('alkohol', instance.drinks_alcohol)
        instance.uses_drugs = validated_data.get('drogen', instance.uses_drugs)
        instance.context = validated_data.get('kontext', instance.context).strip() or instance.context
        instance.status = validated_data.get('status', instance.status)
        instance.note = validated_data.get('notiz', instance.note).strip()
        instance.save()
        return instance


class PatientCreateSerializer(PatientInputSerializer):
    """Alias für bestehende Imports und bestehende View-Logik."""


class PatientFrontendSerializer(serializers.ModelSerializer):
    """Gibt Patienten im bestehenden Frontend-Format aus."""

    class Meta:
        model = Patient
        fields = ['id']

    def to_representation(self, instance):
        """Formt das normalisierte Modell in das Angular-ViewModel um."""
        reports = list(instance.lab_reports.annotate(value_count=Count('values', distinct=True), review_count=Count('review_candidates', distinct=True)).filter(Q(value_count__gt=0) | Q(review_count__gt=0)).order_by('-report_date', '-created_at'))
        open_reviews = sum(open_review_count(report) for report in reports)
        latest_report = reports[0] if reports else None
        released_report = instance.patient_reports.filter(status=PatientReport.Status.RELEASED).order_by('-report_date').first()
        visible_status = patient_status(instance, reports, open_reviews)
        return {
            'id': instance.public_id,
            'nummer': instance.number,
            'name': instance.display_name,
            'vorname': instance.first_name,
            'nachname': instance.last_name,
            'geburtsdatum': format_date(instance.birth_date),
            'geschlecht': instance.sex,
            'gewichtKg': decimal_to_number(instance.weight_kg),
            'groesseCm': instance.height_cm,
            'lebensstil': instance.lifestyle,
            'nichtrauchen': instance.non_smoker,
            'alkohol': instance.drinks_alcohol,
            'drogen': instance.uses_drugs,
            'kontext': instance.context,
            'quelle': instance.source,
            'status': visible_status,
            'befunde': len(reports),
            'offeneReviews': open_reviews,
            'letzterBefund': format_date(latest_report.report_date) if latest_report else 'kein Befund',
            'berichtStatus': released_report.total_status if released_report else 'keine Daten',
            'notiz': instance.note,
            'befundListe': [self.report_to_dict(report) for report in reports],
        }

    def report_to_dict(self, report):
        """Formt einen Befund für die Patientenkarten um."""
        return {
            'id': report.public_id,
            'name': report.name,
            'datum': format_date(report.report_date),
            'status': report_status(report),
            'werte': report.values.count(),
            'offeneReviews': open_review_count(report),
        }
