# apps/reports/translation.py

"""Lokale Übersetzung vollständiger Patientenberichte mit Argos Translate."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError


class TranslationUnavailable(APIException):
    """Signalisiert eine fehlende lokale Engine oder ein fehlendes Sprachmodell."""

    status_code = 503
    default_detail = "Die lokale Übersetzungsengine oder das benötigte Sprachmodell ist nicht installiert."
    default_code = "translation_unavailable"


PROTECTED_PATTERN = re.compile(r"(?<!\w)(?:[-+]?\d+(?:[.,]\d+)?(?:\s*[–-]\s*[-+]?\d+(?:[.,]\d+)?)?|\{\{[^{}]+\}\})(?!\w)")
TOKEN_LEAK_PATTERN = re.compile(r"(?:GLBPROTECTED|GLBGLOSSARY|\{\{[^{}]+\}\})", re.IGNORECASE)
NON_TRANSLATABLE_TEMPLATE_KEYS = {"sprache", "marke", "code"}
PROTECTED_VALUE_FIELDS = ("key", "wert", "einheit", "referenzMin", "referenzMax", "status", "trend", "verlauf")


def translate_report(report_data: dict, target_language: str) -> dict:
    """Übersetzt ausschließlich die druckbare Berichtsvorschau."""
    source_language = settings.GLOBI_TRANSLATION_SOURCE_LANGUAGE
    target = str(target_language or "").strip().lower()
    if not settings.GLOBI_TRANSLATION_ENABLED:
        raise ValidationError("Die lokale Berichtübersetzung ist deaktiviert.")
    if target not in settings.GLOBI_TRANSLATION_LANGUAGES:
        raise ValidationError("Die gewünschte Zielsprache ist nicht freigegeben.")
    if not report_data.get("istDruckbar") or report_data.get("reviewWerte", 0) > 0:
        raise ValidationError("Ein Bericht darf erst ohne offene Reviews übersetzt werden.")

    translator = _load_argos_translator(source_language, target)
    glossary = _load_glossary(source_language, target)
    translated = copy.deepcopy(report_data)
    template = translated.get("template", {})
    template["bericht"] = _translate_structure(template.get("bericht", {}), translator, glossary)
    template["statusLabels"] = _translate_structure(template.get("statusLabels", {}), translator, glossary)
    template["prioritaetLabels"] = _translate_structure(template.get("prioritaetLabels", {}), translator, glossary)
    template["sprache"] = target

    for key in ("gesamtstatus", "gesamttext", "disclaimer"):
        translated[key] = _translate_text(translated.get(key, ""), translator, glossary)

    for item in translated.get("werte", []):
        for key in ("name", "gruppe", "erklaerung", "hinweis"):
            item[key] = _translate_text(item.get(key, ""), translator, glossary)

    for item in translated.get("kategorien", []):
        item["name"] = _translate_text(item.get("name", ""), translator, glossary)

    for item in translated.get("empfehlungen", []):
        item["titel"] = _translate_text(item.get("titel", ""), translator, glossary)
        item["text"] = _translate_text(item.get("text", ""), translator, glossary)

    translated["fragen"] = [_translate_text(item, translator, glossary) for item in translated.get("fragen", [])]
    translated["quellen"] = [
        {
            **item,
            "bereich": _translate_text(item.get("bereich", ""), translator, glossary),
            "titel": _translate_text(item.get("titel", ""), translator, glossary),
        }
        for item in translated.get("quellen", [])
    ]
    translated["uebersetzung"] = {
        "quelle": source_language,
        "ziel": target,
        "engine": "argos-translate",
        "maschinell": True,
    }
    _validate_translation(report_data, translated)
    return translated


def _load_argos_translator(source_language: str, target_language: str):
    """Lädt eine direkte oder von Argos zusammengesetzte lokale Sprachroute."""
    try:
        import argostranslate.translate
    except ImportError as error:
        raise TranslationUnavailable("Argos Translate ist lokal noch nicht installiert.") from error

    installed_languages = argostranslate.translate.get_installed_languages()
    source = next((item for item in installed_languages if item.code == source_language), None)
    target = next((item for item in installed_languages if item.code == target_language), None)
    if source is None or target is None:
        raise TranslationUnavailable("Das benötigte lokale Argos-Sprachmodell ist nicht installiert.")

    translation = source.get_translation(target)
    if translation is None:
        raise TranslationUnavailable(f"Für {source_language} → {target_language} ist kein lokaler Übersetzungsweg verfügbar.")
    return translation


def _load_glossary(source_language: str, target_language: str) -> dict[str, str]:
    """Lädt das kontrollierte medizinische Glossar."""
    path = Path(settings.GLOBI_TRANSLATION_GLOSSARY)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get(source_language, {}).get(target_language, {})


def _translate_structure(value: Any, translator, glossary: dict[str, str], key: str = "") -> Any:
    """Übersetzt rekursiv sichtbare Texte innerhalb der Druckvorlage."""
    if isinstance(value, dict):
        return {
            item_key: item_value if item_key in NON_TRANSLATABLE_TEMPLATE_KEYS else _translate_structure(item_value, translator, glossary, item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_translate_structure(item, translator, glossary, key) for item in value]
    if isinstance(value, str):
        return _translate_text(value, translator, glossary)
    return value


def _translate_text(text: str, translator, glossary: dict[str, str]) -> str:
    """Übersetzt Text segmentiert, ohne interne Tokens an das Modell zu senden."""
    value = str(text or "")
    if not value.strip():
        return value

    protected_segments = _collect_protected_segments(value, glossary)
    if not protected_segments:
        return _translate_plain_segment(value, translator)

    result: list[str] = []
    cursor = 0
    for start, end, replacement in protected_segments:
        if start > cursor:
            result.append(_translate_plain_segment(value[cursor:start], translator))
        result.append(replacement)
        cursor = end
    if cursor < len(value):
        result.append(_translate_plain_segment(value[cursor:], translator))
    return "".join(result)


def _collect_protected_segments(text: str, glossary: dict[str, str]) -> list[tuple[int, int, str]]:
    """Sammelt Zahlen, Platzhalter und Glossarbegriffe als nicht übersetzte Segmente."""
    segments: list[tuple[int, int, str]] = [(match.start(), match.end(), match.group(0)) for match in PROTECTED_PATTERN.finditer(text)]
    for source, target in sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True):
        for match in re.finditer(re.escape(source), text, flags=re.IGNORECASE):
            segments.append((match.start(), match.end(), target))

    accepted: list[tuple[int, int, str]] = []
    for segment in sorted(segments, key=lambda item: (item[0], -(item[1] - item[0]))):
        if accepted and segment[0] < accepted[-1][1]:
            continue
        accepted.append(segment)
    return accepted


def _translate_plain_segment(value: str, translator) -> str:
    """Übersetzt ein freies Textsegment und erhält äußere Leerzeichen."""
    if not value.strip():
        return value
    leading = value[: len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()) :]
    core = value.strip()
    return f"{leading}{translator.translate(core)}{trailing}"


def _validate_translation(original: dict, translated: dict) -> None:
    """Verwirft Übersetzungen mit verlorenen oder veränderten Berichtsdaten."""
    original_values = original.get("werte", [])
    translated_values = translated.get("werte", [])
    if len(original_values) != len(translated_values):
        raise TranslationUnavailable("Die Übersetzung hat Laborwerte entfernt oder ergänzt.")

    for original_value, translated_value in zip(original_values, translated_values, strict=True):
        for field in PROTECTED_VALUE_FIELDS:
            if original_value.get(field) != translated_value.get(field):
                raise TranslationUnavailable(f"Das geschützte Berichtsfeld '{field}' wurde verändert.")

    if len(original.get("empfehlungen", [])) != len(translated.get("empfehlungen", [])):
        raise TranslationUnavailable("Die Übersetzung hat Empfehlungen entfernt oder ergänzt.")
    if len(original.get("fragen", [])) != len(translated.get("fragen", [])):
        raise TranslationUnavailable("Die Übersetzung hat Fragen entfernt oder ergänzt.")

    serialized = json.dumps(translated, ensure_ascii=False)
    if TOKEN_LEAK_PATTERN.search(serialized):
        raise TranslationUnavailable("Die Übersetzung enthält nicht aufgelöste Schutzmarkierungen.")
