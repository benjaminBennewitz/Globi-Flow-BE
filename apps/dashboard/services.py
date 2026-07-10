# apps/dashboard/services.py

"""Aggregierte API-Services für Dashboard und Übersicht."""

from datetime import date
from django.db.models import Count, Q
from django.utils import timezone
from apps.imports.models import ImportJob, ImportLog
from apps.imports.presenters import import_job_to_frontend
from apps.knowledge.models import KnowledgeEntry
from apps.knowledge.presenters import knowledge_to_frontend
from apps.labs.models import LabReport, LabValue, ReviewCandidate
from apps.labs.presenters import average_confidence, group_summary, lab_value_to_dashboard, review_entry_to_frontend, trend_series
from apps.patients.models import Patient
from apps.patients.serializers import PatientFrontendSerializer
from apps.reports.models import PatientReport
from apps.reports.presenters import build_patient_report_preview


OPEN_REVIEW_STATUSES = [ReviewCandidate.Status.OPEN, ReviewCandidate.Status.BLOCKED]
UNCHECKED_IMPORT_STATUSES = [ImportJob.Status.WAITING, ImportJob.Status.ANALYZING, ImportJob.Status.ERROR]


def tag_offset(value) -> int:
    """Berechnet einen kompakten Tagabstand für Frontend-Filter.

    Args:
        value: Zu verarbeitender Eingabewert.

    Returns:
        Rückgabewert vom Typ ``int``.
    """
    if value is None:
        return 0
    local_date = timezone.localtime(value).date() if hasattr(value, 'tzinfo') else value
    return max(0, (timezone.localdate() - local_date).days)


def zeit_label(value) -> str:
    """Formatiert einen Zeitpunkt für das Aktivitätsprotokoll.

    Args:
        value: Zu verarbeitender Eingabewert.

    Returns:
        Rückgabewert vom Typ ``str``.
    """
    if value is None:
        return 'unbekannt'
    return timezone.localtime(value).strftime('%d.%m.%Y · %H:%M')


def non_empty_reports():
    """Lädt nur Befunde, die Laborwerte oder Reviewarbeit enthalten.
    """
    return LabReport.objects.annotate(value_count=Count('values', distinct=True), review_count=Count('review_candidates', distinct=True)).filter(Q(value_count__gt=0) | Q(review_count__gt=0))


def latest_values() -> list[LabValue]:
    """Lädt die Werte aus dem neuesten nicht-leeren Befund.

    Returns:
        Rückgabewert vom Typ ``list[LabValue]``.
    """
    report = non_empty_reports().prefetch_related('values__analyte__group', 'values__unit', 'values__reference_range').order_by('-report_date', '-created_at').first()
    if not report:
        return []
    return list(report.values.select_related('analyte__group', 'unit', 'reference_range'))


def review_queryset():
    """Lädt offene oder blockierende Review-Kandidaten.
    """
    return ReviewCandidate.objects.select_related('report__patient', 'analyte__group', 'corrected_unit', 'reference_range').filter(status__in=OPEN_REVIEW_STATUSES).order_by('status', 'confidence', '-updated_at')


def unchecked_import_queryset():
    """Lädt ungeprüfte, laufende oder fehlerhafte Importjobs.
    """
    return ImportJob.objects.select_related('patient').prefetch_related('steps', 'datasets', 'logs').filter(status__in=UNCHECKED_IMPORT_STATUSES).order_by('-created_at')


def overview_detail_item(kind: str, item) -> dict:
    """Formt Review- oder Importobjekte für KPI-Overlays.

    Args:
        kind: Wert für ``kind``.
        item: Wert für ``item``.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    if kind == 'review':
        patient = item.report.patient
        return {
            'id': item.public_id,
            'titel': item.analyte.display_name,
            'beschreibung': f'{patient.display_name} · {item.report.report_date.strftime("%d.%m.%Y")} · {item.confidence}% Confidence',
            'patientId': patient.public_id,
            'patientName': patient.display_name,
            'befundId': item.report.public_id,
            'route': '/review',
            'status': 'kritisch' if item.status == ReviewCandidate.Status.BLOCKED else 'warnung',
            'datum': item.updated_at.isoformat() if item.updated_at else '',
        }

    patient_name = item.patient.display_name if item.patient else item.test_person_label or 'Keine Testperson'
    return {
        'id': item.public_id,
        'titel': item.filename,
        'beschreibung': f'{patient_name} · {item.get_status_display()} · {item.progress}% Fortschritt',
        'patientId': item.patient.public_id if item.patient else '',
        'patientName': patient_name,
        'befundId': '',
        'route': '/importe',
        'status': 'kritisch' if item.status == ImportJob.Status.ERROR else 'warnung',
        'datum': item.created_at.isoformat() if item.created_at else '',
    }


def build_dringende_hinweise(review_items: list[ReviewCandidate], import_items: list[ImportJob]) -> list[dict]:
    """Erzeugt aktuelle Hinweise aus echten Review- und Importdaten.

    Args:
        review_items: Wert für ``review_items``.
        import_items: Wert für ``import_items``.

    Returns:
        Rückgabewert vom Typ ``list[dict]``.
    """
    hinweise = []
    for candidate in review_items[:8]:
        patient = candidate.report.patient
        hinweise.append({
            'id': candidate.public_id,
            'titel': f'{candidate.analyte.display_name} prüfen',
            'beschreibung': f'{patient.display_name} · Befund {candidate.report.report_date.strftime("%d.%m.%Y")} · Status {candidate.get_status_display()}',
            'seit': candidate.created_at.strftime('%d.%m.%Y') if candidate.created_at else 'unbekannt',
            'status': 'kritisch' if candidate.status == ReviewCandidate.Status.BLOCKED else 'warnung',
            'route': '/review',
            'patientId': patient.public_id,
            'patientName': patient.display_name,
            'befundId': candidate.report.public_id,
            'targetId': candidate.public_id,
        })

    for job in import_items.filter(status=ImportJob.Status.ERROR)[:4]:
        hinweise.append({
            'id': job.public_id,
            'titel': 'Importfehler prüfen',
            'beschreibung': f'{job.filename} · {job.error_message or job.pipeline_step}',
            'seit': job.created_at.strftime('%d.%m.%Y') if job.created_at else 'unbekannt',
            'status': 'kritisch',
            'route': '/importe',
            'patientId': job.patient.public_id if job.patient else '',
            'patientName': job.patient.display_name if job.patient else job.test_person_label,
            'befundId': '',
            'targetId': job.public_id,
        })

    return hinweise[:10]


def build_aktivitaeten() -> list[dict]:
    """Erzeugt ein aktuelles Aktivitätsprotokoll aus Importen, Review und Berichten.

    Returns:
        Rückgabewert vom Typ ``list[dict]``.
    """
    entries = []

    for log in ImportLog.objects.select_related('job__patient').order_by('-created_at')[:20]:
        entries.append({
            'sortValue': log.created_at,
            'id': log.public_id,
            'zeitpunkt': zeit_label(log.created_at),
            'tagOffset': tag_offset(log.created_at),
            'titel': log.title,
            'beschreibung': log.description or log.job.filename,
            'status': 'erledigt' if log.status in {ImportJob.Status.DONE, 'erledigt', 'abgeschlossen'} else 'info',
        })

    for candidate in ReviewCandidate.objects.select_related('report__patient', 'analyte').exclude(status=ReviewCandidate.Status.OPEN).order_by('-updated_at')[:20]:
        status_label = candidate.get_status_display()
        entries.append({
            'sortValue': candidate.updated_at,
            'id': f'activity-{candidate.public_id}',
            'zeitpunkt': zeit_label(candidate.updated_at),
            'tagOffset': tag_offset(candidate.updated_at),
            'titel': f'Review {status_label.lower()}',
            'beschreibung': f'{candidate.analyte.display_name} · {candidate.report.patient.display_name} · Befund {candidate.report.report_date.strftime("%d.%m.%Y")}',
            'status': 'erledigt' if candidate.status in {ReviewCandidate.Status.CORRECTED, ReviewCandidate.Status.CONFIRMED, ReviewCandidate.Status.DISCARDED} else 'warnung',
        })

    for report in PatientReport.objects.select_related('patient', 'lab_report').order_by('-updated_at')[:10]:
        entries.append({
            'sortValue': report.updated_at,
            'id': f'activity-{report.public_id}',
            'zeitpunkt': zeit_label(report.updated_at),
            'tagOffset': tag_offset(report.updated_at),
            'titel': 'Patientenbericht aktualisiert',
            'beschreibung': f'{report.patient.display_name} · Befund {report.report_date.strftime("%d.%m.%Y")}',
            'status': 'erledigt' if report.status == PatientReport.Status.RELEASED else 'info',
        })

    entries.sort(key=lambda item: item['sortValue'] or timezone.now(), reverse=True)
    return [{key: value for key, value in item.items() if key != 'sortValue'} for item in entries[:30]]


def build_health_months() -> list[dict]:
    """Berechnet Monatszahlen mit vollständigen Monatsachsen für stabile Verlaufsgrafiken.

    Returns:
        Rückgabewert vom Typ ``list[dict]``.
    """
    month_labels = {1: 'Jan', 2: 'Feb', 3: 'Mär', 4: 'Apr', 5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Dez'}
    current_year = date.today().year
    years = {current_year - 2, current_year - 1, current_year}
    reports = list(non_empty_reports().prefetch_related('values', 'review_candidates').order_by('report_date'))

    for report in reports:
        years.add(report.report_date.year)

    months: dict[tuple[int, int], dict] = {
        (year, month): {'jahr': year, 'monat': month, 'label': month_labels[month], 'unauffaellig': 0, 'auffaellig': 0}
        for year in sorted(years)
        for month in range(1, 13)
    }

    for report in reports:
        key = (report.report_date.year, report.report_date.month)
        item = months[key]
        has_issue = report.values.filter(status__in=[LabValue.Status.HIGH, LabValue.Status.LOW, LabValue.Status.REVIEW]).exists() or report.review_candidates.filter(status__in=OPEN_REVIEW_STATUSES).exists()
        if has_issue:
            item['auffaellig'] += 1
        else:
            item['unauffaellig'] += 1

    return [months[key] for key in sorted(months)]


def build_dashboard_view() -> dict:
    """Baut die komplette Startansicht für das bestehende Frontend.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    values = latest_values()
    review_candidates = review_queryset()[:10]
    knowledge_entries = KnowledgeEntry.objects.select_related('analyte__group').prefetch_related('sources', 'versions')[:50]
    import_jobs = ImportJob.objects.select_related('patient').prefetch_related('steps', 'datasets', 'logs')[:10]
    return {
        'kennzahlen': {
            'befunde': non_empty_reports().count(),
            'laborwerte': LabValue.objects.count(),
            'review': review_queryset().count(),
            'berichte': PatientReport.objects.filter(status='freigegeben').count(),
            'confidence': average_confidence(values),
        },
        'importjobs': [import_job_to_frontend(job) for job in import_jobs],
        'laborwerte': [lab_value_to_dashboard(value) for value in values],
        'gruppen': group_summary(values),
        'trends': trend_series(values),
        'reviewEintraege': [review_entry_to_frontend(candidate) for candidate in review_candidates],
        'wissenseintraege': [knowledge_to_frontend(entry) for entry in knowledge_entries],
        'patientenbericht': build_patient_report_preview(),
    }


def build_overview_view() -> dict:
    """Baut die aggregierte Praxisübersicht aus aktuellen DB-Daten.

    Returns:
        Rückgabewert vom Typ ``dict``.
    """
    review_items = list(review_queryset()[:30])
    import_items = unchecked_import_queryset()
    import_items_list = list(import_items[:30])
    import_detail_items = [overview_detail_item('import', job) for job in import_items_list]
    review_count = review_queryset().count()
    return {
        'kennzahlen': {
            'patientenGesamt': Patient.objects.count(),
            'berichteGesamt': non_empty_reports().count(),
            'importeGeprueft': ImportJob.objects.filter(status=ImportJob.Status.DONE).count(),
            'importeUngeprueft': import_items.count(),
            'berichteFreigegeben': PatientReport.objects.filter(status=PatientReport.Status.RELEASED).count(),
            'reviewOffen': review_count,
        },
        'gesundheitsverlauf': build_health_months(),
        'dringendeHinweise': build_dringende_hinweise(review_items, import_items),
        'aktivitaeten': build_aktivitaeten(),
        'ungepruefteImporte': import_detail_items,
        'reviewOffenListe': [overview_detail_item('review', candidate) for candidate in review_items],
    }


def build_patient_list() -> list[dict]:
    """Gibt Patienten im Frontendformat aus.

    Returns:
        Rückgabewert vom Typ ``list[dict]``.
    """
    queryset = Patient.objects.prefetch_related('lab_reports__values', 'lab_reports__review_candidates', 'patient_reports')
    return PatientFrontendSerializer(queryset, many=True).data
