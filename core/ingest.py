import pdfplumber

# Minimum chars from normal extraction to skip OCR (avoids OCR for clearly text-based PDFs)
_MIN_TEXT_LEN = 50


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF using pdfplumber (text layer only)."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t.strip():
                text_parts.append(t)
    return "\n\n".join(text_parts).strip()


def _run_ocr(pdf_path: str) -> str:
    """Run OCR on PDF pages using pdf2image + pytesseract. Requires system: poppler, tesseract."""
    import importlib

    pdf2image = importlib.import_module("pdf2image")
    pytesseract = importlib.import_module("pytesseract")
    convert_from_path = pdf2image.convert_from_path

    images = convert_from_path(pdf_path)
    parts = []
    for img in images:
        text = pytesseract.image_to_string(img)
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts).strip()


def extract_text_from_pdf_with_ocr(pdf_path: str) -> tuple[str, bool]:
    """
    Extract text from PDF. If normal extraction is empty or very short, try OCR (scanned PDF).
    Returns (text, used_ocr). used_ocr is True only when OCR was actually run.
    OCR requires: pip install pdf2image pytesseract, and system poppler + tesseract-ocr.
    """
    text = extract_text_from_pdf(pdf_path)
    if text and len(text.strip()) >= _MIN_TEXT_LEN:
        return text, False
    try:
        ocr_text = _run_ocr(pdf_path)
        if ocr_text:
            return ocr_text, True
    except Exception:
        pass
    return text, False