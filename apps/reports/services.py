# apps/reports/services.py

"""Services für die Erzeugung lokaler Patientenberichte."""

from django.db.models import Q
from django.utils import timezone
from apps.knowledge.models import KnowledgeSource
from apps.labs.models import LabReport, LabValue, ReviewCandidate
from apps.reports.models import PatientReport, ReportQuestion, ReportRecommendation, ReportSection, ReportSource


DISCLAIMER = 'Diese Auswertung strukturiert Laborwerte und ersetzt keine Diagnose, Therapieentscheidung oder ärztliche Beratung.'


def report_values_queryset(lab_report: LabReport):
    """Lädt Laborwerte mit allen Relationen für Bericht und Zähler.

    Args:
        lab_report: Wert für ``lab_report``.
    """
    return lab_report.values.select_related('analyte__group', 'unit', 'reference_range', 'analyte__knowledge_entry')


def open_review_candidates(lab_report: LabReport):
    """Lädt offene oder blockierte Review-Kandidaten eines Befunds.

    Args:
        lab_report: Wert für ``lab_report``.
    """
    return lab_report.review_candidates.select_related('analyte__group', 'lab_value').filter(status__in=[ReviewCandidate.Status.OPEN, ReviewCandidate.Status.BLOCKED])


def review_value_ids(lab_report: LabReport) -> set[int]:
    """Ermittelt Laborwert-IDs, die fachlich noch geprüft werden müssen.

    Args:
        lab_report: Wert für ``lab_report``.

    Returns:
        Rückgabewert vom Typ ``set[int]``.
    """
    review_filter = Q(status=LabValue.Status.REVIEW) | Q(
        review_status=LabValue.ReviewStatus.REVIEW)
    ids = set(report_values_queryset(lab_report).filter(
        review_filter).values_list('id', flat=True))
    ids.update(candidate.lab_value_id for candidate in open_review_candidates(
        lab_report) if candidate.lab_value_id)
    return ids


def report_counts(lab_report: LabReport) -> dict[str, int]:
    """Berechnet Berichtszähler direkt aus aktuellen Laborwerten und Review-Kandidaten.

    Args:
        lab_report: Wert für ``lab_report``.

    Returns:
        Rückgabewert vom Typ ``dict[str, int]``.
    """
    values = report_values_queryset(lab_report)
    value_ids_in_review = review_value_ids(lab_report)
    open_candidates_without_value = open_review_candidates(
        lab_report).filter(lab_value__isnull=True).count()
    stable_values = values.exclude(id__in=value_ids_in_review)
    review_count = len(value_ids_in_review) + open_candidates_without_value
    return {
        'total': values.count() + open_candidates_without_value,
        'checked': stable_values.count(),
        'normal': stable_values.filter(status=LabValue.Status.NORMAL).count(),
        'abnormal': stable_values.filter(status__in=[LabValue.Status.HIGH, LabValue.Status.LOW]).count(),
        'review': review_count,
    }


def has_open_review_items(lab_report: LabReport) -> bool:
    """Prüft, ob ein Befund noch offene Review-Arbeit enthält.

    Args:
        lab_report: Wert für ``lab_report``.

    Returns:
        Rückgabewert vom Typ ``bool``.
    """
    return report_counts(lab_report)['review'] > 0


def report_status_text(counts: dict[str, int]) -> str:
    """Erzeugt ein verständliches Statuslabel.

    Args:
        counts: Wert für ``counts``.

    Returns:
        Rückgabewert vom Typ ``str``.
    """
    if counts['review'] > 0:
        return 'Review offen'
    if counts['abnormal'] > 0:
        return 'Auffällige Werte vorhanden'
    return 'Unauffällige Werte'


def report_summary_text(counts: dict[str, int]) -> str:
    """Erzeugt einen nicht-diagnostischen Kurztext.

    Args:
        counts: Wert für ``counts``.

    Returns:
        Rückgabewert vom Typ ``str``.
    """
    if counts['review'] > 0:
        return 'Der Befund enthält noch prüfpflichtige Werte und ist noch nicht für den finalen Druck freigegeben.'
    if counts['abnormal'] > 0:
        return f'Der Befund ist ärztlich geprüft. {counts["abnormal"]} von {counts["total"]} Werten liegen außerhalb des Referenzbereichs und sollten im Arztgespräch eingeordnet werden.'
    return f'Der Befund ist ärztlich geprüft. Die dargestellten {counts["total"]} Werte liegen im vorliegenden Testdatensatz im Referenzbereich.'


def ensure_patient_report(lab_report: LabReport, release: bool = False) -> PatientReport:
    """Erstellt oder aktualisiert den Patientenbericht zu einem Laborbefund.

    Args:
        lab_report: Wert für ``lab_report``.
        release: Wert für ``release``.

    Returns:
        Rückgabewert vom Typ ``PatientReport``.

    Side Effects:
        Verändert persistierte Anwendungsdaten innerhalb des beschriebenen Workflows.
    """
    lab_report = LabReport.objects.select_related('patient').prefetch_related('values__analyte__group', 'values__unit', 'values__reference_range',
                                                                              'values__analyte__knowledge_entry', 'review_candidates__analyte__group', 'review_candidates__lab_value').get(id=lab_report.id)
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


def abnormal_label(value: LabValue) -> str:
    """Gibt eine patiententaugliche Richtung für einen auffälligen Wert zurück.

    Args:
        value: Zu verarbeitender Eingabewert.

    Returns:
        Rückgabewert vom Typ ``str``.
    """
    if value.status == LabValue.Status.HIGH:
        return 'erhöhten'
    if value.status == LabValue.Status.LOW:
        return 'erniedrigten'
    return 'auffälligen'


def rebuild_report_children(report: PatientReport, lab_report: LabReport, counts: dict[str, int]) -> None:
    """Ersetzt abhängige Berichtsinhalte kontrolliert aus aktuellen Befunddaten.

    Args:
        report: Betroffener Labor- oder Patientenbericht.
        lab_report: Wert für ``lab_report``.
        counts: Wert für ``counts``.

    Side Effects:
        Verändert persistierte Anwendungsdaten innerhalb des beschriebenen Workflows.
    """
    report.sections.all().delete()
    report.questions.all().delete()
    report.recommendations.all().delete()
    report.sources.all().delete()

    value_ids_in_review = review_value_ids(lab_report)
    stable_values = report_values_queryset(
        lab_report).exclude(id__in=value_ids_in_review)
    abnormal_values = list(stable_values.filter(status__in=[LabValue.Status.HIGH, LabValue.Status.LOW]).select_related(
        'analyte__group', 'unit', 'reference_range').order_by('priority', 'analyte__group__sort_order', 'analyte__display_name'))

    ReportSection.objects.create(report=report, key='zusammenfassung',
                                 title='Zusammenfassung', text=report.summary, sort_order=10)
    ReportSection.objects.create(report=report, key='werte', title='Laborwerte',
                                 text=f'{counts["total"]} Werte insgesamt, {counts["normal"]} unauffällig, {counts["abnormal"]} auffällig, {counts["review"]} Reviewwerte.', sort_order=20)

    for index, value in enumerate(abnormal_values[:6], start=1):
        ReportRecommendation.objects.create(report=report, public_id=f'empfehlung-{report.public_id}-{index}', title=f'{value.analyte.display_name} ärztlich einordnen',
                                            text=f'Der {abnormal_label(value)} Wert sollte im Zusammenhang mit Beschwerden, Verlauf und weiteren Befunden ärztlich bewertet werden.', priority=ReportRecommendation.Priority.NOTICE, sort_order=index)

    for index, value in enumerate(abnormal_values[:8], start=1):
        direction = 'erhöht' if value.status == LabValue.Status.HIGH else 'erniedrigt'
        ReportQuestion.objects.create(report=report, public_id=f'frage-{report.public_id}-{index}',
                                      question=f'Wie relevant ist der {direction}e Wert {value.analyte.display_name} in meinem Gesamtbefund und sollte er kontrolliert werden?', area=value.analyte.group.name, sort_order=index)

    if not abnormal_values:
        ReportQuestion.objects.create(report=report, public_id=f'frage-{report.public_id}-standard',
                                      question='Gibt es unauffällige Werte, die ich langfristig weiter beobachten sollte?', area='Allgemein', sort_order=1)

    source_ids = set()
    for value in report_values_queryset(lab_report).all():
        knowledge = getattr(value.analyte, 'knowledge_entry', None)
        if not knowledge:
            continue
        for source in KnowledgeSource.objects.filter(entry=knowledge):
            source_key = f'{source.title}|{source.source_type}|{source.source_date}'
            if source_key in source_ids:
                continue
            source_ids.add(source_key)
            ReportSource.objects.create(report=report, public_id=f'quelle-{report.public_id}-{len(source_ids)}',
                                        area=value.analyte.display_name, title=source.title, source_date=source.source_date)

    if not source_ids:
        ReportSource.objects.create(report=report, public_id=f'quelle-{report.public_id}-demo', area='Allgemein',
                                    title='Globi Flow Demo-Wissensbasis', source_date=str(timezone.localdate().year))
