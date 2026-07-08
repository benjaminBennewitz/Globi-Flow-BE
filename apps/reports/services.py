# apps/reports/services.py

"""Services für die Erzeugung lokaler Patientenberichte."""

from django.db.models import Q
from django.utils import timezone
from apps.knowledge.models import KnowledgeSource
from apps.labs.models import LabReport, LabValue, ReviewCandidate
from apps.reports.models import PatientReport, ReportQuestion, ReportRecommendation, ReportSection, ReportSource


DISCLAIMER = 'Diese Auswertung strukturiert Laborwerte und ersetzt keine Diagnose, Therapieentscheidung oder ärztliche Beratung.'


def report_counts(lab_report: LabReport) -> dict[str, int]:
    """Berechnet Berichtszähler direkt aus den geprüften Laborwerten."""
    values = lab_report.values.all()
    review_filter = Q(status=LabValue.Status.REVIEW) | Q(review_status=LabValue.ReviewStatus.REVIEW)
    return {
        'checked': values.filter(review_status=LabValue.ReviewStatus.CHECKED).count(),
        'normal': values.filter(status=LabValue.Status.NORMAL).exclude(review_filter).count(),
        'abnormal': values.filter(status__in=[LabValue.Status.HIGH, LabValue.Status.LOW]).exclude(review_filter).count(),
        'review': values.filter(review_filter).count(),
    }


def has_open_review_items(lab_report: LabReport) -> bool:
    """Prüft, ob ein Befund noch offene Review-Arbeit enthält."""
    open_candidates = lab_report.review_candidates.filter(status__in=[ReviewCandidate.Status.OPEN, ReviewCandidate.Status.BLOCKED]).exists()
    review_values = lab_report.values.filter(review_status=LabValue.ReviewStatus.REVIEW).exists()
    return open_candidates or review_values


def report_status_text(counts: dict[str, int]) -> str:
    """Erzeugt ein verständliches Statuslabel."""
    if counts['review'] > 0:
        return 'Review offen'
    if counts['abnormal'] > 0:
        return 'Auffällige Werte vorhanden'
    return 'Unauffällige Werte'


def report_summary_text(counts: dict[str, int]) -> str:
    """Erzeugt einen nicht-diagnostischen Kurztext."""
    if counts['review'] > 0:
        return 'Der Befund enthält noch prüfpflichtige Werte und ist noch nicht für den finalen Druck freigegeben.'
    if counts['abnormal'] > 0:
        return 'Der Befund ist ärztlich geprüft. Einzelne Werte liegen außerhalb des Referenzbereichs und sollten im Arztgespräch eingeordnet werden.'
    return 'Der Befund ist ärztlich geprüft. Die dargestellten Werte liegen im vorliegenden Testdatensatz im Referenzbereich.'


def ensure_patient_report(lab_report: LabReport, release: bool = False) -> PatientReport:
    """Erstellt oder aktualisiert den Patientenbericht zu einem Laborbefund."""
    lab_report = LabReport.objects.select_related('patient').prefetch_related('values__analyte__group', 'values__unit', 'values__reference_range', 'values__analyte__knowledge_entry', 'review_candidates').get(id=lab_report.id)
    counts = report_counts(lab_report)
    status = PatientReport.Status.READY if counts['review'] == 0 else PatientReport.Status.DRAFT
    if release and counts['review'] == 0:
        status = PatientReport.Status.RELEASED
    report, _ = PatientReport.objects.update_or_create(
        public_id=f'patient-report-{lab_report.public_id}',
        defaults={
            'patient': lab_report.patient,
            'lab_report': lab_report,
            'report_date': lab_report.report_date,
            'version': '1.0',
            'status': status,
            'total_status': report_status_text(counts),
            'total_text': report_summary_text(counts),
            'summary': report_summary_text(counts),
            'checked_values': counts['checked'],
            'normal_values': counts['normal'],
            'abnormal_values': counts['abnormal'],
            'review_values': counts['review'],
            'disclaimer': DISCLAIMER,
        },
    )
    rebuild_report_children(report, lab_report, counts)
    return report


def rebuild_report_children(report: PatientReport, lab_report: LabReport, counts: dict[str, int]) -> None:
    """Ersetzt abhängige Berichtsinhalte kontrolliert aus aktuellen Befunddaten."""
    report.sections.all().delete()
    report.questions.all().delete()
    report.recommendations.all().delete()
    report.sources.all().delete()

    ReportSection.objects.create(report=report, key='zusammenfassung', title='Zusammenfassung', text=report.summary, sort_order=10)
    ReportSection.objects.create(report=report, key='werte', title='Laborwerte', text=f'{counts["checked"]} geprüfte Werte, {counts["abnormal"]} auffällige Werte, {counts["review"]} Reviewwerte.', sort_order=20)

    abnormal_values = list(lab_report.values.filter(status__in=[LabValue.Status.HIGH, LabValue.Status.LOW]).select_related('analyte__group')[:6])
    for index, value in enumerate(abnormal_values, start=1):
        ReportRecommendation.objects.create(report=report, public_id=f'empfehlung-{report.public_id}-{index}', title=f'{value.analyte.display_name} ärztlich einordnen', text='Besprechen Sie diesen Wert im nächsten Arztgespräch. Die Auswertung stellt keine Diagnose.', priority=ReportRecommendation.Priority.NOTICE, sort_order=index)
        ReportQuestion.objects.create(report=report, public_id=f'frage-{report.public_id}-{index}', question=f'Welche Bedeutung hat der Wert {value.analyte.display_name} in meinem Gesamtbefund?', area=value.analyte.group.name, sort_order=index)

    if not abnormal_values:
        ReportQuestion.objects.create(report=report, public_id=f'frage-{report.public_id}-standard', question='Gibt es Werte, die ich langfristig weiter beobachten sollte?', area='Allgemein', sort_order=1)

    source_ids = set()
    for value in lab_report.values.select_related('analyte').all():
        knowledge = getattr(value.analyte, 'knowledge_entry', None)
        if not knowledge:
            continue
        for source in KnowledgeSource.objects.filter(entry=knowledge):
            source_key = f'{source.title}|{source.source_type}|{source.source_date}'
            if source_key in source_ids:
                continue
            source_ids.add(source_key)
            ReportSource.objects.create(report=report, public_id=f'quelle-{report.public_id}-{len(source_ids)}', area=value.analyte.display_name, title=source.title, source_date=source.source_date)

    if not source_ids:
        ReportSource.objects.create(report=report, public_id=f'quelle-{report.public_id}-demo', area='Allgemein', title='Globi Flow Demo-Wissensbasis', source_date=str(timezone.localdate().year))
