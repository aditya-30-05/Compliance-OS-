"""
Document processing service — PDF, DOCX, TXT extraction with OCR support.
Supports PyMuPDF (fitz), pdfplumber, python-docx, and Pytesseract for OCR.
"""

import os
import uuid
import io
from typing import Optional
from backend.config import settings
from backend.utils.logger import logger
from backend.utils.sanitizer import sanitize_filename

# Optional imports for OCR
try:
    import pytesseract
    from PIL import Image
    import pdf2image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


ALLOWED_EXTENSIONS = set(settings.ALLOWED_EXTENSIONS.split(","))
MAX_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
    """Validate file type and size. Returns (is_valid, error_message)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}"
    if file_size > MAX_SIZE_BYTES:
        return False, f"File too large ({file_size / 1024 / 1024:.1f}MB). Max: {settings.MAX_UPLOAD_SIZE_MB}MB"
    return True, ""


def save_uploaded_file(file_content: bytes, original_filename: str) -> tuple[str, str]:
    """Save file to disk. Returns (stored_path, file_type)."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_name = sanitize_filename(original_filename)
    ext = os.path.splitext(safe_name)[1].lower()
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_name)

    with open(stored_path, "wb") as f:
        f.write(file_content)

    logger.info(f"File saved: {stored_path} ({len(file_content)} bytes)")
    return stored_path, ext.lstrip(".")


def extract_text(file_path: str, file_type: str) -> tuple[str, int]:
    """
    Extract text from file.
    Automatically detects scanned PDFs and applies OCR if text layer is missing.
    Returns (extracted_text, page_count).
    """
    file_type = file_type.lower().lstrip(".")
    text = ""
    page_count = 0

    if file_type == "pdf":
        text, page_count = _extract_pdf(file_path)
        # If extraction yielded very little text, it might be a scanned PDF
        if len(text.strip()) < 100 * page_count and HAS_OCR:
            logger.info("PDF appears to be scanned. Initiating OCR pipeline...")
            ocr_text = _run_ocr_pipeline(file_path)
            if len(ocr_text) > len(text):
                text = ocr_text
    elif file_type in ("docx", "doc"):
        text, page_count = _extract_docx(file_path)
    elif file_type == "txt":
        text, page_count = _extract_txt(file_path)

    return text.strip(), page_count


def _extract_pdf(file_path: str) -> tuple[str, int]:
    text = ""
    page_count = 0
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        page_count = len(doc)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        return text, page_count
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return "", 0


def _run_ocr_pipeline(file_path: str) -> str:
    """Multi-page OCR using pdf2image and pytesseract."""
    if not HAS_OCR:
        logger.warning("OCR requested but dependencies (pytesseract, pdf2image) are not installed.")
        return ""

    try:
        # Convert PDF to images
        images = pdf2image.convert_from_path(file_path)
        full_text = []
        
        for i, image in enumerate(images):
            # Preprocessing: Convert to grayscale for better OCR
            image = image.convert('L')
            page_text = pytesseract.image_to_string(image)
            full_text.append(f"--- Page {i+1} ---\n{page_text}")
            
        logger.info(f"OCR completed: {len(images)} pages processed.")
        return "\n\n".join(full_text)
    except Exception as e:
        logger.error(f"OCR pipeline failed: {e}")
        return ""


def _extract_docx(file_path: str) -> tuple[str, int]:
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        word_count = len(text.split())
        return text, max(1, word_count // 250)
    except Exception as e:
        logger.error(f"DOCX extraction failed: {e}")
        return "", 0


def _extract_txt(file_path: str) -> tuple[str, int]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        word_count = len(text.split())
        return text, max(1, word_count // 250)
    except Exception as e:
        logger.error(f"TXT extraction failed: {e}")
        return "", 0
