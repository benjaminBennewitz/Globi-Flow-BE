# apps/imports/pdf_analysis.py

"""Lokale PDF-Textanalyse und OCR-Fallback ohne externe Cloud-Dienste."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from django.conf import settings


@dataclass(frozen=True)
class PdfAnalysisResult:
    """Ergebnis der lokalen PDF-Analyse."""

    text: str
    analysis_type: str
    ocr_required: bool
    ocr_error: str = ""


def extract_pdf_text(path: str | Path) -> str:
    """Extrahiert die vorhandene PDF-Textschicht lokal."""
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    reader = PdfReader(str(path))
    chunks = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()


def prepare_ocr_image(image):
    """Optimiert eine PDF-Seite für Tabellen-OCR."""
    from PIL import ImageEnhance, ImageFilter, ImageOps

    prepared = ImageOps.grayscale(image)
    prepared = ImageOps.autocontrast(prepared)
    prepared = ImageEnhance.Contrast(prepared).enhance(1.35)
    prepared = prepared.filter(ImageFilter.SHARPEN)
    return prepared


def extract_ocr_text(path: str | Path) -> tuple[str, str]:
    """Extrahiert Text per lokalem Tesseract-OCR-Fallback."""
    if not getattr(settings, "OCR_ENABLED", False):
        return "", "OCR ist in den Backend-Settings deaktiviert."

    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception as exc:
        return "", f"OCR-Abhängigkeiten fehlen: {exc}"

    tesseract_cmd = getattr(settings, "TESSERACT_CMD", "").strip()
    poppler_path = getattr(settings, "POPPLER_PATH", "").strip()
    ocr_languages = getattr(settings, "OCR_LANGUAGES", "eng").strip() or "eng"
    ocr_dpi = int(getattr(settings, "OCR_DPI", 300) or 300)

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    chunks = []
    try:
        kwargs = {"dpi": ocr_dpi}
        if poppler_path:
            kwargs["poppler_path"] = poppler_path

        images = convert_from_path(str(path), **kwargs)
        config = "--oem 3 --psm 4 -c preserve_interword_spaces=1"
        for page_number, image in enumerate(images, start=1):
            prepared = prepare_ocr_image(image)
            page_text = pytesseract.image_to_string(prepared, lang=ocr_languages, config=config)
            if page_text.strip():
                chunks.append(f"--- OCR Seite {page_number} ---\n{page_text.strip()}")
    except Exception as exc:
        return "", f"OCR konnte nicht ausgeführt werden: {exc}"

    return "\n".join(chunks).strip(), ""


def analyze_pdf(path: str | Path, ocr_started_callback: Callable[[], None] | None = None) -> PdfAnalysisResult:
    """Führt Textschichtanalyse aus und nutzt OCR nur bei Bedarf."""
    text = extract_pdf_text(path)
    if len(text) >= 80:
        return PdfAnalysisResult(text=text, analysis_type="textschicht", ocr_required=False)

    if ocr_started_callback:
        ocr_started_callback()

    ocr_text, error = extract_ocr_text(path)
    if ocr_text:
        return PdfAnalysisResult(text=ocr_text, analysis_type="ocr", ocr_required=True)

    return PdfAnalysisResult(
        text=text,
        analysis_type="ocr",
        ocr_required=True,
        ocr_error=error or "Keine verwertbare Textschicht erkannt.",
    )
