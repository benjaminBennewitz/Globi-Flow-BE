# apps/core/management/commands/seed_demo_data.py

"""Überträgt die vorhandenen Angular-Mockdaten in die normalisierte Datenbank."""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.dashboard.models import DashboardActivity, DashboardHealthMonth, DashboardNotice
from apps.imports.models import ImportDataset, ImportJob, ImportLog, ImportStep
from apps.knowledge.models import KnowledgeEntry, KnowledgeSource, KnowledgeVersion
from apps.labs.models import LabGroup, LabAnalyte, LabReport, LabUnit, LabValue, ReferenceRange, ReviewCandidate
from apps.patients.models import Patient
from apps.reports.models import PatientReport, ReportQuestion, ReportRecommendation, ReportSection, ReportSource

SEED_PATH = Path(__file__).resolve().parents[2] / 'seeds' / 'frontend_mocks.json'


def parse_date(value: str | None) -> date | None:
    """Parst deutsche und ISO-Datumsangaben aus den Mockdaten."""
    if not value or value == 'kein Befund':
        return None
    value = value.split('·')[0].strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            from datetime import datetime
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def decimal(value, fallback='0') -> Decimal:
    """Wandelt Seed-Zahlen robust in Decimal um."""
    if value is None:
        value = fallback
    return Decimal(str(value).replace(',', '.'))


def slug(value: str) -> str:
    """Erzeugt einen einfachen stabilen Schlüssel."""
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', '/': '_'}
    result = value.lower().strip()
    for source, target in replacements.items():
        result = result.replace(source, target)
    return '_'.join(''.join(char if char.isalnum() else ' ' for char in result).split())


class Command(BaseCommand):
    """Seedet die Frontend-Mockdaten normalisiert in PostgreSQL."""

    help = 'Überträgt die vorhandenen Angular-Mockdaten in die lokale Datenbank.'

    def add_arguments(self, parser):
        """Registriert Command-Argumente."""
        parser.add_argument('--reset', action='store_true', help='Löscht vorhandene Demo-Daten vor dem Seed.')

    @transaction.atomic
    def handle(self, *args, **options):
        """Führt den Seed aus."""
        data = json.loads(SEED_PATH.read_text(encoding='utf-8'))
        if options['reset']:
            self.reset_data()
        self.seed_patients(data['MOCK_PATIENTEN'])
        self.seed_analytes(data)
        self.seed_reports_and_values(data)
        self.seed_review(data['MOCK_REVIEW']['kandidaten'])
        self.seed_imports(data['MOCK_IMPORTJOBS'])
        self.seed_knowledge(data['MOCK_WISSENSEINTRAEGE'])
        self.seed_patient_report(data['MOCK_BERICHT'], data['MOCK_PATIENTENBERICHT'])
        self.seed_dashboard(data['MOCK_UEBERSICHT'])
        self.stdout.write(self.style.SUCCESS('Demo-Daten wurden normalisiert angelegt.'))

    def reset_data(self) -> None:
        """Löscht alle fachlichen Demo-Daten in abhängiger Reihenfolge."""
        DashboardActivity.objects.all().delete()
        DashboardNotice.objects.all().delete()
        DashboardHealthMonth.objects.all().delete()
        ReportSource.objects.all().delete()
        ReportRecommendation.objects.all().delete()
        ReportQuestion.objects.all().delete()
        ReportSection.objects.all().delete()
        PatientReport.objects.all().delete()
        KnowledgeSource.objects.all().delete()
        KnowledgeVersion.objects.all().delete()
        KnowledgeEntry.objects.all().delete()
        ImportLog.objects.all().delete()
        ImportDataset.objects.all().delete()
        ImportStep.objects.all().delete()
        ImportJob.objects.all().delete()
        ReviewCandidate.objects.all().delete()
        LabValue.objects.all().delete()
        LabReport.objects.all().delete()
        ReferenceRange.objects.all().delete()
        LabAnalyte.objects.all().delete()
        LabGroup.objects.all().delete()
        LabUnit.objects.all().delete()
        Patient.objects.all().delete()

    def seed_patients(self, patients: list[dict]) -> None:
        """Legt Testpersonen an."""
        for item in patients:
            Patient.objects.update_or_create(
                public_id=item['id'],
                defaults={
                    'number': item['nummer'],
                    'first_name': item['vorname'],
                    'last_name': item['nachname'],
                    'display_name': item['name'],
                    'birth_date': parse_date(item.get('geburtsdatum')),
                    'sex': item['geschlecht'],
                    'weight_kg': decimal(item.get('gewichtKg')) if item.get('gewichtKg') is not None else None,
                    'height_cm': item.get('groesseCm'),
                    'lifestyle': item.get('lebensstil', ''),
                    'context': item.get('kontext', ''),
                    'source': item.get('quelle', 'demo'),
                    'status': item.get('status', 'aktiv'),
                    'note': item.get('notiz', ''),
                },
            )

    def ensure_analyte(self, key: str, name: str, group_name: str) -> LabAnalyte:
        """Lädt oder erstellt Gruppe und Laborwert."""
        group, _ = LabGroup.objects.get_or_create(key=slug(group_name), defaults={'name': group_name})
        analyte, _ = LabAnalyte.objects.update_or_create(key=key, defaults={'display_name': name, 'group': group, 'aliases': [name, key.replace('_', ' ')]})
        return analyte

    def ensure_unit(self, code: str) -> LabUnit:
        """Lädt oder erstellt eine Einheit."""
        unit, _ = LabUnit.objects.get_or_create(code=code, defaults={'normalized_code': code.lower()})
        return unit

    def ensure_reference(self, analyte: LabAnalyte, unit: LabUnit, lower, upper) -> ReferenceRange:
        """Lädt oder erstellt einen Referenzbereich."""
        reference, _ = ReferenceRange.objects.get_or_create(analyte=analyte, unit=unit, sex=ReferenceRange.Sex.ANY, age_min=None, age_max=None, lower=decimal(lower), upper=decimal(upper), defaults={'source_note': 'Frontend-Demo-Seed'})
        return reference

    def seed_analytes(self, data: dict) -> None:
        """Sammelt alle Laborwertdefinitionen aus den Mockdaten."""
        sources = []
        sources.extend(data.get('MOCK_LABORWERTE', []))
        sources.extend(data.get('MOCK_AUSWERTUNG', {}).get('werte', []))
        sources.extend(data.get('MOCK_BERICHT', {}).get('werte', []))
        for item in data.get('MOCK_WISSENSEINTRAEGE', []):
            sources.append({'key': item['laborwertKey'], 'name': item['anzeigename'], 'gruppe': item['kategorie']})
        for item in sources:
            analyte = self.ensure_analyte(item['key'], item.get('name') or item.get('anzeigename'), item.get('gruppe') or item.get('kategorie'))
            if 'einheit' in item:
                unit = self.ensure_unit(item['einheit'])
                self.ensure_reference(analyte, unit, item.get('referenzMin', 0), item.get('referenzMax', 999999))

    def seed_reports_and_values(self, data: dict) -> None:
        """Legt Befunde und Laborwerte aus Patienten-, Auswertungs- und Berichtsmocks an."""
        patients_by_id = {patient.public_id: patient for patient in Patient.objects.all()}
        for patient_item in data['MOCK_PATIENTEN']:
            patient = patients_by_id[patient_item['id']]
            for report_item in patient_item.get('befundListe', []):
                LabReport.objects.update_or_create(public_id=report_item['id'], defaults={'patient': patient, 'name': report_item['name'], 'report_date': parse_date(report_item['datum']), 'status': report_item['status'], 'source': patient_item.get('quelle', 'demo')})

        main_patient = Patient.objects.order_by('id').first()
        latest_report = LabReport.objects.order_by('-report_date').first()
        if not main_patient or not latest_report:
            return

        dates = ['2025-06-12', '2025-09-12', '2025-12-12', '2026-03-14', '2026-06-12']
        for date_value in dates:
            if date_value == '2026-06-12':
                continue
            LabReport.objects.get_or_create(public_id=f'befund-verlauf-{date_value}', defaults={'patient': main_patient, 'name': f'Verlaufsbefund {date_value}', 'report_date': parse_date(date_value), 'status': LabReport.Status.RELEASED, 'source': 'verlauf'})

        for item in data['MOCK_AUSWERTUNG']['werte']:
            self.seed_value_series(main_patient, item, dates)

        for item in data['MOCK_BERICHT']['werte']:
            report = latest_report
            analyte = self.ensure_analyte(item['key'], item['name'], item['gruppe'])
            unit = self.ensure_unit(item['einheit'])
            reference = self.ensure_reference(analyte, unit, item['referenzMin'], item['referenzMax'])
            LabValue.objects.update_or_create(public_id=f'wert-{report.public_id}-{item["key"]}', defaults={'report': report, 'analyte': analyte, 'unit': unit, 'reference_range': reference, 'value': decimal(item['wert']), 'status': item['status'], 'priority': 'hoch' if item['status'] == 'hoch' else 'mittel' if item['status'] in {'niedrig', 'review'} else 'niedrig', 'review_status': 'review' if item['status'] == 'review' else 'geprueft', 'confidence': 95, 'hint': item.get('hinweis', '')})

    def seed_value_series(self, patient: Patient, item: dict, dates: list[str]) -> None:
        """Legt eine Verlaufserie als normalisierte Befundwerte an."""
        analyte = self.ensure_analyte(item['key'], item['name'], item['gruppe'])
        unit = self.ensure_unit(item['einheit'])
        reference = self.ensure_reference(analyte, unit, item['referenzMin'], item['referenzMax'])
        for index, point in enumerate(item.get('verlauf', [])):
            report_date = parse_date(point['datum'])
            report = LabReport.objects.filter(patient=patient, report_date=report_date).first()
            if report is None:
                report = LabReport.objects.create(public_id=f'befund-verlauf-{point["datum"]}', patient=patient, name=f'Verlaufsbefund {point["datum"]}', report_date=report_date, status=LabReport.Status.RELEASED, source='verlauf')
            is_latest = index == len(item.get('verlauf', [])) - 1
            LabValue.objects.update_or_create(public_id=f'wert-{report.public_id}-{item["key"]}', defaults={'report': report, 'analyte': analyte, 'unit': unit, 'reference_range': reference, 'value': decimal(point['wert']), 'status': item['status'] if is_latest else 'normal', 'priority': item.get('prioritaet', 'niedrig') if is_latest else 'niedrig', 'review_status': item.get('reviewStatus', 'geprueft') if is_latest else 'geprueft', 'confidence': item.get('confidence', 95), 'hint': item.get('hinweis', '') if is_latest else 'Historischer Verlaufspunkt.'})

    def seed_review(self, candidates: list[dict]) -> None:
        """Legt Review-Kandidaten an."""
        for item in candidates:
            report = LabReport.objects.get(public_id=item['befundId'])
            analyte = LabAnalyte.objects.get(key=item['laborwertKey'])
            unit = self.ensure_unit(item['korrigierteEinheit'])
            reference = self.ensure_reference(analyte, unit, item['referenzMin'], item['referenzMax'])
            lab_value = LabValue.objects.filter(report=report, analyte=analyte).first()
            ReviewCandidate.objects.update_or_create(public_id=item['id'], defaults={'report': report, 'lab_value': lab_value, 'analyte': analyte, 'raw_name': item['erkannterName'], 'raw_value': item['erkannterWert'], 'corrected_value': decimal(item['korrigierterWert']), 'raw_unit': item['erkannteEinheit'], 'corrected_unit': unit, 'reference_range': reference, 'original_text': item['originalText'], 'original_label': item['originalLabel'], 'confidence': item['confidence'], 'status': item['status'], 'source': item['quelle'], 'comment': item.get('kommentar', ''), 'parser_hints': item.get('parserHinweise', []), 'checks': item.get('checks', [])})

    def seed_imports(self, jobs: list[dict]) -> None:
        """Legt Importjobs mit Schritten, Datasets und Logs an."""
        patient = Patient.objects.order_by('id').first()
        for item in jobs:
            job, _ = ImportJob.objects.update_or_create(public_id=item['id'], defaults={'patient': patient, 'filename': item['dateiname'], 'test_person_label': item.get('testperson', ''), 'analysis_type': item['analyseArt'], 'status': item['status'], 'progress': item['fortschritt'], 'pipeline_step': item['pipelineSchritt'], 'ocr_status': item['ocrStatus'], 'recognized_values': item['erkannteWerte'], 'uncertain_values': item['unsichereWerte'], 'confidence': item['confidence'], 'error_message': item.get('fehlermeldung', '')})
            job.steps.all().delete()
            job.datasets.all().delete()
            job.logs.all().delete()
            for index, step in enumerate(item.get('schritte', []), start=1):
                ImportStep.objects.create(job=job, key=step['key'], name=step['name'], description=step['beschreibung'], status=step['status'], is_completed=step['abgeschlossen'], sort_order=index)
            for dataset in item.get('datasets', []):
                ImportDataset.objects.create(public_id=dataset['id'], job=job, name=dataset['name'], values_count=dataset['werte'], review_count=dataset['review'], confidence=dataset['confidence'], status=dataset['status'])
            for log in item.get('logEintraege', []):
                ImportLog.objects.create(public_id=log['id'], job=job, time_label=log['zeitpunkt'], title=log['titel'], description=log['beschreibung'], status=log['status'])

    def seed_knowledge(self, entries: list[dict]) -> None:
        """Legt Wissenseinträge, Quellen und Versionen an."""
        for item in entries:
            analyte = self.ensure_analyte(item['laborwertKey'], item['anzeigename'], item['kategorie'])
            entry, _ = KnowledgeEntry.objects.update_or_create(analyte=analyte, defaults={'patient_short_text': item['patientKurztext'], 'patient_long_text': item['patientLangtext'], 'doctor_information': item['arztinformation'], 'causes_low': item['ursachenNiedrig'], 'causes_high': item['ursachenHoch'], 'influencing_factors': item['einflussfaktoren'], 'notes': item['hinweise'], 'disclaimer': item['disclaimer'], 'version': item['version'], 'status': item['status'], 'changed_by': item['geaendertVon'], 'changed_at_label': item['geaendertAm']})
            entry.sources.all().delete()
            entry.versions.all().delete()
            for source in item.get('quellen', []):
                KnowledgeSource.objects.create(public_id=source['id'], entry=entry, title=source['titel'], source_type=source['typ'], source_date=source['stand'], reference=source['referenz'], note=source['hinweis'])
            for version in item.get('versionen', []):
                KnowledgeVersion.objects.create(entry=entry, version=version['version'], date_label=version['datum'], changed_by=version['bearbeitetVon'], note=version['notiz'])

    def seed_patient_report(self, print_report: dict, patient_report: dict) -> None:
        """Legt Patientenbericht und Druckbericht an."""
        patient = Patient.objects.order_by('id').first()
        lab_report = LabReport.objects.order_by('-report_date').first()
        report, _ = PatientReport.objects.update_or_create(public_id=print_report['id'], defaults={'patient': patient, 'lab_report': lab_report, 'report_date': parse_date(print_report['berichtsdatum']), 'version': print_report['version'], 'status': PatientReport.Status.RELEASED, 'total_status': print_report['gesamtstatus'], 'total_text': print_report['gesamttext'], 'summary': patient_report.get('zusammenfassung', ''), 'checked_values': print_report['gepruefteWerte'], 'normal_values': print_report['normaleWerte'], 'abnormal_values': print_report['auffaelligeWerte'], 'review_values': print_report['reviewWerte'], 'disclaimer': print_report['disclaimer']})
        report.sections.all().delete()
        report.questions.all().delete()
        report.recommendations.all().delete()
        report.sources.all().delete()
        for index, section in enumerate(patient_report.get('abschnitte', []), start=1):
            ReportSection.objects.create(report=report, key=section['key'], title=section['titel'], text=section['text'], sort_order=index)
        for index, question in enumerate(patient_report.get('fragen', []), start=1):
            ReportQuestion.objects.create(public_id=question.get('id', f'frage-{index}'), report=report, question=question.get('frage', question if isinstance(question, str) else ''), area=question.get('bereich', '') if isinstance(question, dict) else '', sort_order=index)
        for index, recommendation in enumerate(print_report.get('empfehlungen', []), start=1):
            ReportRecommendation.objects.create(public_id=recommendation['id'], report=report, title=recommendation['titel'], text=recommendation['text'], priority=recommendation['prioritaet'], sort_order=index)
        for source in print_report.get('quellen', []):
            ReportSource.objects.create(public_id=source['id'], report=report, area=source['bereich'], title=source['titel'], source_date=source['stand'])

    def seed_dashboard(self, overview: dict) -> None:
        """Legt aggregierte Übersichts-Mockdaten an."""
        for item in overview.get('gesundheitsverlauf', []):
            DashboardHealthMonth.objects.update_or_create(year=item['jahr'], month=item['monat'], defaults={'label': item['label'], 'normal_count': item['unauffaellig'], 'abnormal_count': item['auffaellig']})
        for item in overview.get('dringendeHinweise', []):
            DashboardNotice.objects.update_or_create(public_id=item['id'], defaults={'title': item['titel'], 'description': item['beschreibung'], 'since': item['seit'], 'status': item['status']})
        for item in overview.get('aktivitaeten', []):
            DashboardActivity.objects.update_or_create(public_id=item['id'], defaults={'time_label': item['zeitpunkt'], 'day_offset': item['tagOffset'], 'title': item['titel'], 'description': item['beschreibung'], 'status': item['status']})
