# apps/core/management/commands/reset_clinical_demo_data.py

"""Setzt die klinischen Demo-Daten auf einen konsistenten Teststand zurück."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.core.management.commands.demo_clinical_data import (
    ANALYTES,
    DEMO_PATIENTS,
    DISCLAIMER,
    GROUPS,
    REPORT_DATES,
    REPORT_NAMES,
    REPORT_SUMMARIES,
    VALUE_SERIES,
    decimal,
    value_priority,
    value_status,
)
from apps.imports.models import ImportDataset, ImportJob, ImportLog, ImportStep
from apps.labs.models import LabAnalyte, LabGroup, LabReport, LabUnit, LabValue, ReferenceRange, ReviewCandidate
from apps.patients.models import Patient
from apps.reports.models import PatientReport, ReportQuestion, ReportRecommendation, ReportSection, ReportSource

class Command(BaseCommand):
    """Setzt die klinischen Demo-Daten reproduzierbar zurück."""

    help = 'Setzt die fiktiven klinischen Demo-Daten für die sechs Testpersonen zurück.'

    def add_arguments(self, parser):
        """Registriert optionale Command-Argumente."""
        parser.add_argument('--keep-knowledge', action='store_true', default=True,
                            help='Wissensbasis bleibt erhalten. Dieses Flag ist aktuell der Standard.')

    @transaction.atomic
    def handle(self, *args, **options):
        """Führt den Reset und Seed in einer Transaktion aus."""
        self.reset_clinical_data()
        patients = self.seed_patients()
        self.seed_reports_values_imports_and_patient_reports(patients)
        self.stdout.write(self.style.SUCCESS(
            'Klinische Demo-Daten wurden zurückgesetzt.'))

    def reset_clinical_data(self) -> None:
        """Löscht patientenbezogene Demo-Daten, ohne die Wissensbasis zu entfernen."""
        ReportSource.objects.all().delete()
        ReportRecommendation.objects.all().delete()
        ReportQuestion.objects.all().delete()
        ReportSection.objects.all().delete()
        PatientReport.objects.all().delete()
        ImportLog.objects.all().delete()
        ImportDataset.objects.all().delete()
        ImportStep.objects.all().delete()
        ImportJob.objects.all().delete()
        ReviewCandidate.objects.all().delete()
        LabValue.objects.all().delete()
        LabReport.objects.all().delete()
        Patient.objects.all().delete()

    def seed_patients(self) -> dict[str, Patient]:
        """Legt die sechs fiktiven Testpersonen an."""
        patients = {}
        for item in DEMO_PATIENTS:
            patient = Patient.objects.create(
                public_id=item['public_id'],
                number=item['number'],
                first_name=item['first_name'],
                last_name=item['last_name'],
                display_name=f"{item['first_name']} {item['last_name']}",
                birth_date=item['birth_date'],
                sex=item['sex'],
                weight_kg=item['weight_kg'],
                height_cm=item['height_cm'],
                lifestyle=item['lifestyle'],
                non_smoker=item.get('non_smoker', False),
                drinks_alcohol=item.get('drinks_alcohol', False),
                uses_drugs=item.get('uses_drugs', False),
                context=item['context'],
                source=item['source'],
                status=item['status'],
                note=item['note'],
            )
            patients[item['public_id']] = patient
        return patients

    def seed_reports_values_imports_and_patient_reports(self, patients: dict[str, Patient]) -> None:
        """Legt Verlaufsbefunde, Laborwerte, Importjobs und Patientenberichte an."""
        for patient_id, series in VALUE_SERIES.items():
            patient = patients[patient_id]
            latest_report = None
            for index, report_date in enumerate(REPORT_DATES):
                report = self.create_report(
                    patient, patient_id, report_date, index)
                latest_report = report
                for key, values in series.items():
                    self.create_value(report, key, values[index])
                self.create_import_job(patient, patient_id, report, index)
            if latest_report:
                self.create_patient_report(patient, latest_report, patient_id)

    def create_report(self, patient: Patient, patient_id: str, report_date: date, index: int) -> LabReport:
        """Legt einen stabilen Befundkopf an."""
        public_id = f'befund-{patient_id.replace("patient-", "")}-{report_date.isoformat()}'
        name = REPORT_NAMES[patient_id][index]
        return LabReport.objects.create(public_id=public_id, patient=patient, name=name, report_date=report_date, status=LabReport.Status.RELEASED, source='demo', released_at=timezone.now())

    def create_value(self, report: LabReport, key: str, value: Any) -> None:
        """Legt einen normalisierten Laborwert inklusive Referenz an."""
        display_name, group_key, unit_code, lower, upper = ANALYTES[key]
        analyte = self.ensure_analyte(key, display_name, group_key)
        unit = self.ensure_unit(unit_code)
        reference = self.ensure_reference(analyte, unit, lower, upper)
        amount = decimal(value)
        status = value_status(amount, lower, upper)
        LabValue.objects.create(
            public_id=f'wert-{report.public_id}-{key}'[:64],
            report=report,
            analyte=analyte,
            unit=unit,
            reference_range=reference,
            value=amount,
            status=status,
            priority=value_priority(status, key),
            review_status=LabValue.ReviewStatus.CHECKED,
            confidence=98 if status == LabValue.Status.NORMAL else 93,
            hint=self.value_hint(key, status),
            original_text=f'Demo-Wert {display_name}: {amount} {unit_code}',
        )

    def ensure_analyte(self, key: str, display_name: str, group_key: str) -> LabAnalyte:
        """Lädt oder erstellt Laborwertgruppe und Laborwertdefinition."""
        group_name, sort_order = GROUPS[group_key]
        group_by_name = LabGroup.objects.filter(name=group_name).first()
        group_by_key = LabGroup.objects.filter(key=group_key).first()
        group = group_by_name or group_by_key
        if group_by_name and group_by_key and group_by_name.id != group_by_key.id:
            LabAnalyte.objects.filter(
                group=group_by_key).update(group=group_by_name)
            group_by_key.delete()
            group = group_by_name
        if group is None:
            group = LabGroup.objects.create(
                key=group_key, name=group_name, sort_order=sort_order)
        else:
            group.key = group_key
            group.name = group_name
            group.sort_order = sort_order
            group.save(update_fields=['key', 'name',
                       'sort_order', 'updated_at'])
        analyte, _ = LabAnalyte.objects.update_or_create(key=key, defaults={'display_name': display_name, 'group': group, 'aliases': [
                                                         display_name, key.replace('_', ' ')], 'sort_order': sort_order, 'is_active': True})
        return analyte

    def ensure_unit(self, code: str) -> LabUnit:
        """Lädt oder erstellt eine Einheit."""
        unit, _ = LabUnit.objects.update_or_create(
            code=code, defaults={'normalized_code': code.lower()})
        return unit

    def ensure_reference(self, analyte: LabAnalyte, unit: LabUnit, lower: Decimal, upper: Decimal) -> ReferenceRange:
        """Lädt oder erstellt einen Referenzbereich."""
        reference, _ = ReferenceRange.objects.get_or_create(analyte=analyte, unit=unit, sex=ReferenceRange.Sex.ANY,
                                                            age_min=None, age_max=None, lower=lower, upper=upper, defaults={'source_note': 'Klinischer Demo-Seed'})
        return reference

    def create_import_job(self, patient: Patient, patient_id: str, report: LabReport, index: int) -> None:
        """Legt einen abgeschlossenen Importjob für den Befund an."""
        job = ImportJob.objects.create(
            public_id=f'import-{patient_id.replace("patient-", "")}-{report.report_date.isoformat()}',
            patient=patient,
            filename=report.name,
            test_person_label=patient.display_name,
            analysis_type=ImportJob.AnalysisType.DEMO,
            status=ImportJob.Status.DONE,
            progress=100,
            pipeline_step='Demo-Befund normalisiert angelegt',
            ocr_status=ImportJob.OcrStatus.NOT_REQUIRED,
            recognized_values=report.values.count(),
            uncertain_values=0,
            confidence=97,
        )
        ImportStep.objects.create(job=job, key='normalisierung', name='Normalisierung',
                                  description='Fiktive Demo-Werte wurden normalisiert in die Datenbank übertragen.', status=ImportStep.Status.DONE, is_completed=True, sort_order=1)
        ImportDataset.objects.create(public_id=f'dataset-{job.public_id}', job=job, name='Laborwerte',
                                     values_count=report.values.count(), review_count=0, confidence=97, status=ImportDataset.Status.NORMAL)
        ImportLog.objects.create(public_id=f'log-{job.public_id}', job=job, time_label=f'T-{index}', title='Demo-Befund angelegt',
                                 description=f'{report.name} wurde für {patient.display_name} zurückgesetzt.', status='erledigt')

    def create_patient_report(self, patient: Patient, lab_report: LabReport, patient_id: str) -> None:
        """Legt einen passenden Patientenbericht zum letzten Befund an."""
        values = list(lab_report.values.select_related('analyte__group'))
        abnormal_count = sum(
            1 for value in values if value.status != LabValue.Status.NORMAL)
        normal_count = len(values) - abnormal_count
        total_status, total_text = REPORT_SUMMARIES[patient_id]
        report = PatientReport.objects.create(
            public_id=f'patientenbericht-{patient_id}',
            patient=patient,
            lab_report=lab_report,
            report_date=lab_report.report_date,
            version='1.0',
            status=PatientReport.Status.RELEASED,
            total_status=total_status,
            total_text=total_text,
            summary=total_text,
            checked_values=len(values),
            normal_values=normal_count,
            abnormal_values=abnormal_count,
            review_values=0,
            disclaimer=DISCLAIMER,
        )
        ReportSection.objects.create(
            report=report, key='verlauf', title='Verlauf', text=total_text, sort_order=1)
        ReportSection.objects.create(report=report, key='einordnung', title='Einordnung',
                                     text=self.report_section_text(patient_id), sort_order=2)
        for index, recommendation in enumerate(self.recommendations(patient_id), start=1):
            ReportRecommendation.objects.create(public_id=f'empf-{patient_id}-{index}', report=report,
                                                title=recommendation['title'], text=recommendation['text'], priority=recommendation['priority'], sort_order=index)
        for index, question in enumerate(self.questions(patient_id), start=1):
            ReportQuestion.objects.create(
                public_id=f'frage-{patient_id}-{index}', report=report, question=question, area='Arztgespräch', sort_order=index)
        ReportSource.objects.create(public_id=f'quelle-{patient_id}-1', report=report,
                                    area='Demo', title='Fiktiver Globi-Flow-Demo-Datensatz', source_date='07.2026')

    def value_hint(self, key: str, status: str) -> str:
        """Erzeugt kurze Demo-Hinweise für auffällige Werte."""
        if status == LabValue.Status.NORMAL:
            return 'Unauffälliger Demo-Wert im Referenzbereich.'
        if key in {'crp', 'leukozyten'}:
            return 'Entzündungsmarker im Demo-Verlauf auffällig, ärztlich einordnen.'
        if key in {'tsh', 'ft3', 'ft4'}:
            return 'Schilddrüsenwert auffällig, Verlauf und Symptome ärztlich besprechen.'
        if key in {'ferritin', 'haemoglobin', 'vitamin_d', 'magnesium', 'zink', 'selen'}:
            return 'Mikronährstoff- oder Blutbildwert auffällig, kontrollierte Abklärung empfohlen.'
        return 'Auffälliger Demo-Wert, bitte im Gesamtkontext prüfen.'

    def report_section_text(self, patient_id: str) -> str:
        """Gibt einen erklärenden Abschnitt je Demo-Profil zurück."""
        if patient_id == 'patient-demo-01':
            return 'Mara zeigt den komplexesten Demo-Verlauf. Die Werte sind absichtlich breit angelegt, damit Mineralien, Spurenelemente, Schilddrüse, Entzündung und Stoffwechsel gemeinsam getestet werden können.'
        if patient_id == 'patient-demo-02':
            return 'Jonas dient als Sportprofil. Trainingsrelevante Werte sind enthalten, bleiben aber im unauffälligen Bereich.'
        if patient_id == 'patient-demo-03':
            return 'Lea zeigt leichte Auffälligkeiten, die sich zum letzten Befund deutlich verbessern.'
        return 'Emil zeigt stabile, weitgehend optimale Werte und eignet sich als gesunder Vergleichsfall.'

    def recommendations(self, patient_id: str) -> list[dict[str, str]]:
        """Gibt Berichts-Empfehlungen je Demo-Profil zurück."""
        if patient_id == 'patient-demo-01':
            return [
                {'title': 'Entzündung und Schilddrüse priorisieren', 'text': 'CRP, TSH, fT3 und fT4 sollten zusammen mit Symptomen und Verlauf ärztlich geprüft werden.',
                    'priority': ReportRecommendation.Priority.IMPORTANT},
                {'title': 'Mikronährstoffe kontrollieren', 'text': 'Ferritin, Vitamin D, Magnesium, Zink und Selen sind im Demo-Verlauf auffällig und eignen sich für die Berichtsdarstellung.',
                    'priority': ReportRecommendation.Priority.NOTICE},
            ]
        if patient_id == 'patient-demo-02':
            return [{'title': 'Sportkontext berücksichtigen', 'text': 'CK, Kreatinin und Harnstoff sollten bei Sportlern immer mit Trainingszeitpunkt und Flüssigkeitshaushalt betrachtet werden.', 'priority': ReportRecommendation.Priority.NORMAL}]
        if patient_id == 'patient-demo-03':
            return [{'title': 'Verbesserung bestätigen', 'text': 'Der Trend verbessert sich. Eine Verlaufskontrolle kann die Stabilisierung bestätigen.', 'priority': ReportRecommendation.Priority.NOTICE}]
        return [{'title': 'Stabilen Verlauf erhalten', 'text': 'Die Werte sind im Demo-Verlauf stabil. Regelmäßige Kontrolle reicht als Testfall aus.', 'priority': ReportRecommendation.Priority.NORMAL}]

    def questions(self, patient_id: str) -> list[str]:
        """Gibt passende Fragen für den Patientenbericht zurück."""
        if patient_id == 'patient-demo-01':
            return ['Welche Ursachen kommen für die wiederkehrende Entzündung infrage?', 'Sollten Schilddrüsen- und Mikronährstoffwerte gezielt kontrolliert werden?']
        if patient_id == 'patient-demo-02':
            return ['Wann wurde vor der Blutabnahme trainiert?', 'Sind Flüssigkeitszufuhr und Regeneration ausreichend berücksichtigt?']
        if patient_id == 'patient-demo-03':
            return ['Ist die Verbesserung stabil?', 'Wann ist eine nächste Verlaufskontrolle sinnvoll?']
        return ['Welche Kontrollintervalle sind bei stabilen Werten sinnvoll?']
