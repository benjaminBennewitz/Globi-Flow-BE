# apps/imports/service_persistence.py

"""Persistiert erkannte Laborwerte und synchronisiert den Reviewworkflow."""

from collections import defaultdict
from statistics import mean

from django.conf import settings

from apps.imports.models import ImportDataset, ImportJob
from apps.imports.parser import ParsedLabValue
from apps.imports.service_setup import priority_for_status, slugify_key, unique_public_id
from apps.labs.models import LabAnalyte, LabReport, LabUnit, LabValue, ReferenceRange, ReviewCandidate


def create_datasets(job: ImportJob, saved_values: list[LabValue]) -> None:
    """Erstellt gruppierte Import-Datasets für die UI."""
    grouped: dict[str, list[LabValue]] = defaultdict(list)
    for lab_value in saved_values:
        grouped[lab_value.analyte.group.name].append(lab_value)

    for index, (group_name, values) in enumerate(sorted(grouped.items()), start=1):
        review_count = sum(1 for value in values if value.review_status == LabValue.ReviewStatus.REVIEW)
        confidence = round(mean(value.confidence for value in values)) if values else 0
        ImportDataset.objects.create(public_id=f'dataset-{job.public_id}-{index}', job=job, name=group_name, values_count=len(values), review_count=review_count, confidence=confidence, status=ImportDataset.Status.REVIEW if review_count else ImportDataset.Status.NORMAL)



def deduplicate_parsed_values(parsed_values: list[ParsedLabValue]) -> tuple[list[ParsedLabValue], int]:
    """Entfernt doppelte Parser- oder OCR-Treffer je Laborwert.

    Args:
        parsed_values: Erkannte, noch nicht persistierte Laborwerte.

    Returns:
        Tupel aus eindeutigen Laborwerten und Anzahl verworfener Dubletten.
        Bei konkurrierenden Treffern gewinnt die höhere Confidence und danach
        der Treffer mit dem aussagekräftigeren Originaltext.
    """
    unique_values: dict[str, ParsedLabValue] = {}
    duplicate_count = 0

    for parsed in parsed_values:
        key = slugify_key(parsed.analyte_key or parsed.display_name, 'laborwert')
        existing = unique_values.get(key)

        if existing is None:
            unique_values[key] = parsed
            continue

        duplicate_count += 1
        should_replace = parsed.confidence > existing.confidence
        same_confidence_newer_text = parsed.confidence == existing.confidence and len(parsed.original_text) > len(existing.original_text)

        if should_replace or same_confidence_newer_text:
            unique_values[key] = parsed

    return list(unique_values.values()), duplicate_count





def auto_review_threshold() -> int:
    """Liefert den konfigurierbaren Confidence-Grenzwert für automatische Übernahme."""
    return int(getattr(settings, 'IMPORT_AUTO_REVIEW_CONFIDENCE_THRESHOLD', 90))

def review_hints_for_value(parsed: ParsedLabValue, analysis_type: str, value_status: str) -> list[str]:
    """Ermittelt nachvollziehbare Hinweise für die ärztliche Prüfung.

    Args:
        parsed: Normalisierter Parserkandidat.
        analysis_type: Verwendete Analyseart des Importjobs.
        value_status: Bereits berechneter Laborwertstatus.

    Returns:
        Liste fachlich verständlicher Gründe für die Review-Markierung.
    """
    hints: list[str] = []

    threshold = auto_review_threshold()

    if analysis_type == ImportJob.AnalysisType.OCR and parsed.confidence < threshold:
        hints.append(f'OCR-Import unter {threshold} Prozent Confidence.')
    if value_status == LabValue.Status.REVIEW:
        hints.append('Confidence liegt unter dem Grenzwert für automatische Übernahme.')
    if parsed.confidence < threshold:
        hints.append(f'Erkennungsqualität unter {threshold} Prozent.')
    if not str(parsed.unit or '').strip() or str(parsed.unit or '').strip().lower() == 'ohne einheit':
        hints.append('Einheit konnte nicht sicher erkannt werden.')
    if parsed.reference_min == parsed.reference_max:
        hints.append('Referenzbereich wirkt unvollständig oder unsicher.')

    return hints or ['Automatisch markiert, weil Alias oder Confidence ärztlich geprüft werden sollte.']


def should_review_value(parsed: ParsedLabValue, analysis_type: str, value_status: str) -> bool:
    """Entscheidet, ob ein erkannter Wert in den Review muss."""
    threshold = auto_review_threshold()

    if value_status == LabValue.Status.REVIEW:
        return True
    if parsed.confidence < threshold:
        return True
    if not str(parsed.unit or '').strip() or str(parsed.unit or '').strip().lower() == 'ohne einheit':
        return True
    if parsed.reference_min == parsed.reference_max:
        return True
    return False


def save_lab_value(report: LabReport, analyte: LabAnalyte, unit: LabUnit, reference: ReferenceRange, parsed: ParsedLabValue, value_status: str, review_status: str) -> LabValue:
    """Speichert einen Laborwert idempotent für Befund und Laborwert-Key.

    Args:
        report: Zielbefund des Laborwerts.
        analyte: Normalisierter Laborwertstamm.
        unit: Erkannte oder neu angelegte Einheit.
        reference: Zugeordneter Referenzbereich.
        parsed: Parserkandidat mit Ergebnis und Originaltext.
        value_status: Fachlicher Anzeigezustand des Ergebnisses.
        review_status: Prüfzustand für den Reviewworkflow.

    Returns:
        Neu angelegter oder aktualisierter Laborwert.

    Side Effects:
        Aktualisiert vorhandene Werte desselben Befunds und Laborwert-Keys.
    """
    lab_value, created = LabValue.objects.update_or_create(
        report=report,
        analyte=analyte,
        defaults={
            'public_id': unique_public_id(LabValue, 'wert'),
            'unit': unit,
            'reference_range': reference,
            'value': parsed.value,
            'status': value_status,
            'priority': priority_for_status(value_status),
            'review_status': review_status,
            'confidence': parsed.confidence,
            'hint': 'Aus lokalem Import erkannt.',
            'original_text': parsed.original_text,
        },
    )

    if not created and not lab_value.public_id:
        lab_value.public_id = unique_public_id(LabValue, 'wert')
        lab_value.save(update_fields=['public_id', 'updated_at'])

    return lab_value


def sync_review_candidate(report: LabReport, lab_value: LabValue, analyte: LabAnalyte, unit: LabUnit, reference: ReferenceRange, parsed: ParsedLabValue, source: str, index: int) -> ReviewCandidate:
    """Synchronisiert einen prüfpflichtigen Wert mit der Reviewwarteschlange.

    Args:
        report: Befund des zu prüfenden Werts.
        lab_value: Bereits gespeicherter normalisierter Laborwert.
        analyte: Zugeordneter Laborwertstamm.
        unit: Korrigierbare Einheit.
        reference: Korrigierbarer Referenzbereich.
        parsed: Ursprünglicher Parserkandidat.
        source: Quelle des Kandidaten, beispielsweise OCR oder PDF-Text.
        index: Laufende Nummer für technische Prüfkennungen.

    Returns:
        Neu angelegter oder aktualisierter Review-Kandidat.

    Side Effects:
        Reaktiviert offene Kandidaten, erhält aber bereits bestätigte oder
        korrigierte Entscheidungen.
    """
    candidate = ReviewCandidate.objects.filter(report=report, analyte=analyte, source=source).exclude(status=ReviewCandidate.Status.DISCARDED).order_by('id').first()
    defaults = {
        'lab_value': lab_value,
        'raw_name': parsed.display_name,
        'raw_value': str(parsed.value),
        'corrected_value': parsed.value,
        'raw_unit': parsed.unit,
        'corrected_unit': unit,
        'reference_range': reference,
        'original_text': parsed.original_text,
        'original_label': f'Importzeile {index}',
        'confidence': parsed.confidence,
        'parser_hints': ['Automatisch markiert, weil Alias oder Confidence ärztlich geprüft werden sollte.'],
        'checks': [{'id': f'check-{index}', 'titel': 'Parserprüfung', 'beschreibung': 'Bitte Wert, Einheit und Referenzbereich bestätigen.', 'status': 'pruefen'}],
    }

    if candidate:
        for field, value in defaults.items():
            setattr(candidate, field, value)
        if candidate.status not in {ReviewCandidate.Status.CORRECTED, ReviewCandidate.Status.CONFIRMED}:
            candidate.status = ReviewCandidate.Status.OPEN
        candidate.save(update_fields=[*defaults.keys(), 'status', 'updated_at'])
        return candidate

    return ReviewCandidate.objects.create(public_id=unique_public_id(ReviewCandidate, 'review'), report=report, analyte=analyte, source=source, **defaults)
