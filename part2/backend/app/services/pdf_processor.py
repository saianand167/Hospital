"""
PDF processing using PyMuPDF (fitz).
Determines whether PDF has selectable text or is scanned,
then either extracts text directly or renders pages for OCR.
"""
from typing import List, Tuple
import fitz  # PyMuPDF
from PIL import Image


def is_text_pdf(pdf_bytes: bytes) -> bool:
    """Return True if the PDF contains selectable text."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Corrupted or invalid PDF format: {str(e)}")
        
    for page in doc:
        if page.get_text().strip():
            doc.close()
            return True
    doc.close()
    return False


def extract_text_from_pdf(pdf_bytes: bytes) -> List[Tuple[int, str]]:
    """
    Extract selectable text from a text-based PDF.
    Returns list of (page_number, text).
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Corrupted or invalid PDF format: {str(e)}")

    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        pages.append((i, text))
    doc.close()
    return pages


def render_pdf_pages(pdf_bytes: bytes, dpi: int = 200) -> List[Tuple[int, Image.Image]]:
    """
    Render each PDF page to a PIL image for OCR.
    Returns list of (page_number, PIL Image).
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Corrupted or invalid PDF format: {str(e)}")

    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pages = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pages.append((i, img))
    doc.close()
    return pages
