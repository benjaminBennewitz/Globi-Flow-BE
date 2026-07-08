# apps/imports/pdf_analysis.py

"""Lokale PDF-Textanalyse und OCR-Fallback ohne externe Cloud-Dienste."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from django.conf import settings


@dataclass(frozen=True)
class PdfAnalysisResult:
    """Ergebnis der lokalen PDF-Analyse."""

    text: str
    analysis_type: str
    ocr_required: bool
    ocr_error: str = ''


def extract_pdf_text(path: str | Path) -> str:
    """Extrahiert die vorhandene PDF-Textschicht lokal."""
    try:
        from pypdf import PdfReader
    except Exception:
        return ''

    reader = PdfReader(str(path))
    chunks = []
    for page in reader.pages:
        chunks.append(page.extract_text() or '')
    return '\n'.join(chunks).strip()


def extract_ocr_text(path: str | Path) -> tuple[str, str]:
    """Extrahiert Text per lokalem Tesseract-OCR-Fallback."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception as exc:
        return '', f'OCR-Abhängigkeiten fehlen: {exc}'

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    chunks = []
    try:
        images = convert_from_path(str(path), dpi=220)
        for image in images:
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            chunks.append(pytesseract.image_to_string(image, lang='deu+eng'))
    except Exception as exc:
        return '', f'OCR konnte nicht ausgeführt werden: {exc}'

    return '\n'.join(chunks).strip(), ''


def analyze_pdf(path: str | Path) -> PdfAnalysisResult:
    """Führt Textschichtanalyse aus und nutzt OCR nur bei Bedarf."""
    text = extract_pdf_text(path)
    if len(text) >= 80:
        return PdfAnalysisResult(text=text, analysis_type='textschicht', ocr_required=False)

    ocr_text, error = extract_ocr_text(path)
    if ocr_text:
        return PdfAnalysisResult(text=ocr_text, analysis_type='ocr', ocr_required=True)

    return PdfAnalysisResult(text=text, analysis_type='ocr', ocr_required=True, ocr_error=error or 'Keine verwertbare Textschicht erkannt.')
