# apps/patients/serializers.py

"""Serializer für Testpersonen und Patienten."""

from rest_framework import serializers
from apps.core.utils import decimal_to_number, format_date, public_id
from apps.patients.models import Patient


class PatientInputSerializer(serializers.Serializer):
    """Validiert Testpersonen aus der Angular-App für Create und Update."""

    vorname = serializers.CharField(max_length=80, allow_blank=True, required=False)
    nachname = serializers.CharField(max_length=80, allow_blank=True, required=False)
    nummer = serializers.CharField(max_length=32, allow_blank=True, required=False)
    geburtsdatum = serializers.DateField(required=False, allow_null=True)
    geschlecht = serializers.ChoiceField(choices=Patient.Sex.choices, default=Patient.Sex.UNKNOWN, required=False)
    gewichtKg = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    groesseCm = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=260)
    lebensstil = serializers.CharField(max_length=240, allow_blank=True, required=False)
    notiz = serializers.CharField(allow_blank=True, required=False)
    kontext = serializers.CharField(max_length=240, allow_blank=True, required=False)
    status = serializers.ChoiceField(choices=Patient.Status.choices, required=False)

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
        reports = list(instance.lab_reports.all())
        open_reviews = sum(report.review_candidates.filter(status='offen').count() for report in reports)
        latest_report = reports[0] if reports else None
        released_report = instance.patient_reports.filter(status='freigegeben').first()
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
            'kontext': instance.context,
            'quelle': instance.source,
            'status': instance.status,
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
            'status': report.status,
            'werte': report.values.count(),
            'offeneReviews': report.review_candidates.filter(status='offen').count(),
        }
