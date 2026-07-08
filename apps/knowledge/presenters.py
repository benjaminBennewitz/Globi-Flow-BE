# apps/knowledge/presenters.py

"""Präsentationsfunktionen für Wissenseinträge."""

from apps.knowledge.models import KnowledgeEntry


def knowledge_to_frontend(entry: KnowledgeEntry) -> dict:
    """Gibt einen Wissenseintrag im vorhandenen Angular-Format aus."""
    return {
        'id': f'wissen-{entry.analyte.key}',
        'laborwertKey': entry.analyte.key,
        'anzeigename': entry.analyte.display_name,
        'kategorie': entry.analyte.group.name,
        'patientKurztext': entry.patient_short_text,
        'patientLangtext': entry.patient_long_text,
        'arztinformation': entry.doctor_information,
        'ursachenNiedrig': entry.causes_low,
        'ursachenHoch': entry.causes_high,
        'einflussfaktoren': entry.influencing_factors,
        'hinweise': entry.notes,
        'disclaimer': entry.disclaimer,
        'quellen': [
            {'id': source.public_id, 'titel': source.title, 'typ': source.source_type, 'stand': source.source_date, 'referenz': source.reference, 'hinweis': source.note}
            for source in entry.sources.all()
        ],
        'version': entry.version,
        'status': entry.status,
        'geaendertAm': entry.changed_at_label,
        'geaendertVon': entry.changed_by,
        'versionen': [
            {'version': version.version, 'datum': version.date_label, 'bearbeitetVon': version.changed_by, 'notiz': version.note}
            for version in entry.versions.all()
        ],
    }
