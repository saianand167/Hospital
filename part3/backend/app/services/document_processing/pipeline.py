import os
import re
import uuid
import datetime
import logging
import json
import base64
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
import numpy as np
import requests

logger = logging.getLogger(__name__)

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

from app.config import settings
from app.services.llm_service import grok_service

# Global EasyOCR reader cache (lazy loaded)
_easyocr_reader = None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None and HAS_EASYOCR:
        try:
            logger.info("Initializing EasyOCR reader (CPU)...")
            _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e:
            logger.warning(f"Could not initialize EasyOCR: {e}")
    return _easyocr_reader


# ── 1. OCR Provider ────────────────────────────────────────────────────────────

class OCRResult:
    def __init__(self, text: str, confidence: float):
        self.text = text
        self.confidence = confidence


def preprocess_image_for_tesseract(img: Image.Image) -> List[Image.Image]:
    """Generate preprocessed image variants for robust Tesseract character and number recognition."""
    variants = []
    
    # Variant 1: Enhanced Grayscale + 2x Upscale + Sharpness
    w, h = img.size
    upscaled = img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    gray = upscaled.convert("L")
    enhancer = ImageEnhance.Contrast(gray)
    contrast_img = enhancer.enhance(1.8)
    sharpener = ImageEnhance.Sharpness(contrast_img)
    sharp_img = sharpener.enhance(2.0)
    variants.append(sharp_img)
    
    # Variant 2: High-contrast binarized (Otsu-style)
    try:
        fn = lambda x: 255 if x > 150 else 0
        bin_img = sharp_img.point(fn, mode="1")
        variants.append(bin_img)
    except Exception:
        pass
# ── Tesseract Path Detection ──────────────────────────────────────────────────
if HAS_TESSERACT:
    tesseract_candidates = [
        getattr(settings, "TESSERACT_CMD", ""),
        os.getenv("TESSERACT_CMD", ""),
        r"C:\Users\saian\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\saian\AppData\Local\Tesseract-OCR\tesseract.exe",
        "tesseract"
    ]
    for tc in tesseract_candidates:
        if tc and (os.path.exists(tc) or tc == "tesseract"):
            try:
                pytesseract.pytesseract.tesseract_cmd = tc
                break
            except Exception:
                pass


# ── 1. OCR Provider ────────────────────────────────────────────────────────────

class OCRResult:
    def __init__(self, text: str, confidence: float):
        self.text = text
        self.confidence = confidence


def preprocess_image_for_tesseract(img: Image.Image) -> List[Image.Image]:
    """Generate preprocessed image variants optimized for medical reports & tables."""
    variants = []
    
    # Variant 1: Grayscale + 2x Lanczos Upscale + Contrast Boost + Sharpness
    w, h = img.size
    upscaled = img.resize((max(w * 2, 1600), max(h * 2, 2200)), Image.Resampling.LANCZOS)
    gray = upscaled.convert("L")
    enhancer = ImageEnhance.Contrast(gray)
    contrast_img = enhancer.enhance(1.8)
    sharpener = ImageEnhance.Sharpness(contrast_img)
    sharp_img = sharpener.enhance(2.0)
    variants.append(sharp_img)
    
    # Variant 2: Normal Grayscale with slight contrast enhancement (for crisp scans)
    try:
        norm_gray = img.convert("L")
        norm_enh = ImageEnhance.Contrast(norm_gray).enhance(1.4)
        variants.append(norm_enh)
    except Exception:
        pass
        
    return variants


class DocumentOCRProvider:
    @staticmethod
    def extract_from_image(image_bytes: bytes, filename: str) -> OCRResult:
        """Extract high-accuracy text from image using Tesseract OCR (Primary)."""
        
        # ── 1. PRIMARY: Tesseract OCR (v5.4.0) ─────────────────────────────
        if HAS_TESSERACT:
            try:
                raw_img = Image.open(io.BytesIO(image_bytes))
                preprocessed_variants = preprocess_image_for_tesseract(raw_img)
                
                best_text = ""
                best_conf = 0.85
                
                # Test multiple configurations optimized for tabular reports and column layouts
                configs = [
                    r"--oem 3 --psm 6",  # Assume a single uniform block of text
                    r"--oem 3 --psm 4",  # Assume a single column of text of variable sizes
                    r"--oem 3 --psm 3",  # Fully automatic page segmentation
                    r"--oem 3 --psm 1"   # Automatic page segmentation with OSD
                ]
                
                for p_img in preprocessed_variants:
                    for cfg in configs:
                        try:
                            data = pytesseract.image_to_data(p_img, config=cfg, output_type=pytesseract.Output.DICT)
                            confidences = [float(c) for c in data.get("conf", []) if str(c).strip() not in ("-1", "")]
                            avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.85
                            text = pytesseract.image_to_string(p_img, config=cfg).strip()
                            
                            if len(text) > len(best_text):
                                best_text = text
                                best_conf = avg_conf
                        except Exception:
                            continue
                    if len(best_text) > 100:
                        break

                if best_text and len(best_text.strip()) > 10:
                    logger.info(f"✅ Tesseract OCR extracted {len(best_text)} chars from {filename} (conf: {round(best_conf, 3)})")
                    return OCRResult(text=best_text, confidence=max(round(best_conf, 3), 0.85))
            except Exception as e:
                logger.warning(f"Tesseract OCR failed on {filename} ({e}), trying fallback engines...")

        # ── 2. FALLBACK 1: Groq Vision AI (qwen/qwen3.8-27b) ─────────────
        groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
        if groq_api_key:
            try:
                b64_img = base64.b64encode(image_bytes).decode("utf-8")
                mime = "image/jpeg"
                if filename.lower().endswith(".png"):
                    mime = "image/png"
                elif filename.lower().endswith(".webp"):
                    mime = "image/webp"

                for v_model in ["qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]:
                    try:
                        res = requests.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {groq_api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": v_model,
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "Transcribe and extract ALL text from this medical document image verbatim, preserving all test names, values, units, and reference ranges."
                                            },
                                            {
                                                "type": "image_url",
                                                "image_url": {"url": f"data:{mime};base64,{b64_img}"}
                                            }
                                        ]
                                    }
                                ],
                                "temperature": 0.1
                            },
                            timeout=20
                        )
                        if res.status_code == 200:
                            content = res.json()["choices"][0]["message"]["content"].strip()
                            if "<think>" in content and "</think>" in content:
                                content = content.split("</think>")[-1].strip()
                            if content and len(content) > 10:
                                logger.info(f"Groq Vision ({v_model}) transcribed {len(content)} chars from {filename}")
                                return OCRResult(text=content, confidence=0.95)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Groq Vision fallback error: {e}")

        # ── 3. FALLBACK 2: EasyOCR (Python CPU) ───────────────────────────
        reader = get_easyocr_reader()
        if reader:
            try:
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img_np = np.array(img)
                results = reader.readtext(img_np)
                if results:
                    text_lines = [r[1] for r in results]
                    confidences = [float(r[2]) for r in results]
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0.85
                    extracted_text = "\n".join(text_lines).strip()
                    if extracted_text:
                        logger.info(f"EasyOCR extracted {len(extracted_text)} chars from {filename}")
                        return OCRResult(text=extracted_text, confidence=round(avg_conf, 3))
            except Exception as e:
                logger.warning(f"EasyOCR extraction error on {filename}: {e}")

        # ── 4. Unresolvable Image ──────────────────────────────────────────
        return OCRResult(
            text=f"Uploaded Document: {filename}\n[Image text could not be clearly resolved.]",
            confidence=0.50
        )

    @staticmethod
    def extract_from_pdf(pdf_bytes: bytes, filename: str) -> OCRResult:
        """Extract text from PDF: extracts selectable text or renders pages into high-res images for Tesseract OCR."""
        all_pages_text = []
        avg_confs = []

        # ── Attempt 1: PyMuPDF (fitz) page rendering & OCR ──────────────
        try:
            import pymupdf  # PyMuPDF
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            logger.info(f"Processing PDF '{filename}' with {len(doc)} pages using PyMuPDF + Tesseract...")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                # First check if selectable digital text is available on this page
                page_text = page.get_text().strip()
                
                # If digital text is substantial (> 40 chars), use it directly
                if page_text and len(page_text) > 40:
                    all_pages_text.append(f"--- Page {page_num + 1} ---\n{page_text}")
                    avg_confs.append(0.98)
                else:
                    # Scanned PDF page: render to high-res image (200 DPI) and run Tesseract OCR
                    zoom = 200 / 72.0  # 200 DPI
                    matrix = pymupdf.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=matrix)
                    img_bytes = pix.tobytes("png")
                    
                    ocr_page_res = DocumentOCRProvider.extract_from_image(img_bytes, f"{filename}_page_{page_num + 1}.png")
                    if ocr_page_res.text and len(ocr_page_res.text.strip()) > 10:
                        all_pages_text.append(f"--- Page {page_num + 1} ---\n{ocr_page_res.text}")
                        avg_confs.append(ocr_page_res.confidence)
            
            doc.close()
            
            if all_pages_text:
                combined_text = "\n\n".join(all_pages_text)
                overall_conf = sum(avg_confs) / len(avg_confs) if avg_confs else 0.90
                logger.info(f"✅ Extracted {len(combined_text)} characters across {len(all_pages_text)} pages from {filename}")
                return OCRResult(text=combined_text, confidence=round(overall_conf, 3))
        except Exception as e:
            logger.warning(f"PyMuPDF processing failed on {filename} ({e}), falling back to pypdf...")

        # ── Attempt 2: pypdf text extraction ─────────────────────────────
        if HAS_PYPDF:
            try:
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                pypdf_text = []
                for page_idx, page in enumerate(reader.pages):
                    pt = page.extract_text()
                    if pt and pt.strip():
                        pypdf_text.append(f"--- Page {page_idx + 1} ---\n{pt.strip()}")
                if pypdf_text:
                    full_text = "\n\n".join(pypdf_text)
                    logger.info(f"pypdf extracted {len(full_text)} chars from {filename}")
                    return OCRResult(text=full_text, confidence=0.95)
            except Exception as e:
                logger.warning(f"pypdf extraction error on {filename}: {e}")

        return DocumentOCRProvider.extract_from_image(pdf_bytes, filename)


# ── 2. Structured Data Extractor via Groq AI ─────────────────────────────────

class StructuredDataExtractor:
    @staticmethod
    def extract_structured_data(raw_text: str, document_type: str) -> Dict[str, Any]:
        """Convert extracted real OCR text into structured JSON parameters via Groq AI."""
        if not raw_text or len(raw_text.strip()) < 10:
            return {
                "document_type": document_type,
                "patient_name": "",
                "report_date": "",
                "tests": [],
                "medications": [],
                "impression": "",
                "note": "No text extracted from document"
            }

        prompt = f"""You are an expert clinical laboratory and medical document parameter extraction engine.
DOCUMENT TYPE: {document_type}
RAW OCR EXTRACTED TEXT:
\"\"\"
{raw_text[:8000]}
\"\"\"

CRITICAL INSTRUCTIONS:
1. Extract ALL clinical laboratory tests, investigations, panel values, units, reference ranges, and abnormal status (HIGH, LOW, NORMAL) mentioned in the text.
2. If it's a LAB_REPORT (Biochemistry, Haematology, CBC, LFT, KFT, Renal Panel, Cardiac, etc.):
   - Populate "tests" with an array of objects:
     [{{"test_name": "Name of test/panel", "result_value": "numeric or text value", "unit": "mg/dl or mmol/l or /cu.mm etc", "reference_range": "e.g. 70-140", "status": "HIGH/LOW/NORMAL"}}]
3. If it's a PRESCRIPTION, populate "medications":
     [{{"medicine_name": "...", "dose": "...", "frequency": "...", "duration": "...", "instructions": "..."}}]
4. Extract patient_name, doctor_name, report_date, lab_no, and impression/summary if present.
5. Return ONLY valid, parseable JSON with no markdown backticks and no conversational filler.

Schema:
{{
  "document_type": "{document_type}",
  "patient_name": "...",
  "report_date": "...",
  "doctor_name": "...",
  "lab_no": "...",
  "tests": [
    {{
      "test_name": "...",
      "result_value": "...",
      "unit": "...",
      "reference_range": "...",
      "status": "NORMAL"
    }}
  ],
  "medications": [],
  "impression": "..."
}}
"""
        messages = [
            {"role": "system", "content": "You are a clinical parameter extractor. Return structured JSON only without markdown formatting."},
            {"role": "user", "content": prompt}
        ]

        try:
            resp_str = grok_service._call_groq_api(messages)
            if "<think>" in resp_str and "</think>" in resp_str:
                resp_str = resp_str.split("</think>")[-1].strip()
            s_idx = resp_str.find("{")
            e_idx = resp_str.rfind("}") + 1
            if s_idx != -1 and e_idx != -1:
                parsed = json.loads(resp_str[s_idx:e_idx])
                if isinstance(parsed, dict) and ("tests" in parsed or "medications" in parsed):
                    return parsed
        except Exception as e:
            logger.warning(f"Groq parameter extraction failed ({e}), using robust heuristic parser.")

        # Heuristic fallback for tabular lab parameters
        tests = []
        patient_name = ""
        report_date = ""

        for line in raw_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Extract Patient Name
            if not patient_name:
                m_pat = re.search(r"(?:Name|Patient\s*Name)\s*[\:\-]?\s*([A-Za-z\.\s]{3,30})", line, re.IGNORECASE)
                if m_pat and "HOSPITAL" not in m_pat.group(1).upper() and "DOCTOR" not in m_pat.group(1).upper():
                    patient_name = m_pat.group(1).strip()

            # Extract Date
            if not report_date:
                m_date = re.search(r"(?:Date|Reporting\s*Date|Collection\s*Date)\s*[\:\-]?\s*([0-9\/\-\.]{8,12})", line, re.IGNORECASE)
                if m_date:
                    report_date = m_date.group(1).strip()

            # Match standard lab report table rows: Name, Result Value, Unit, Reference Range
            # e.g.: "Plasma GLUCOSE- Random (Hexokinase) 78 mg/dl [70-140]"
            # e.g.: "Haemoglobin (Photometric) 15.1 g/dl [13.0-17.0]"
            m_tab = re.search(
                r"^([A-Za-z\s\-\(\)\/\*]+?)\s+([0-9\.]+)\s*(#|\*)?\s+([a-zA-Z\/\%\<\>\.\-\^0-9]+)\s+(?:\[|\()?([0-9\.\-\<\>\s]+)(?:\]|\))?",
                line
            )
            if m_tab:
                t_name = m_tab.group(1).strip(" *#-:")
                val = m_tab.group(2).strip()
                unit = m_tab.group(4).strip()
                ref = m_tab.group(5).strip() if m_tab.group(5) else ""
                if len(t_name) > 2 and not t_name.upper().startswith("PAGE"):
                    tests.append({
                        "test_name": t_name,
                        "result_value": val,
                        "unit": unit,
                        "reference_range": ref,
                        "status": "NORMAL"
                    })
                continue

            # Generic "Test: Value Unit" format
            m_gen = re.search(r"([A-Za-z\s\-\(\)]+?)[\:\=]\s*([0-9\.\,]+)\s*([a-zA-Z\/\%\<\>]+)?", line)
            if m_gen:
                t_name = m_gen.group(1).strip(" *#-:")
                if len(t_name) > 2 and not t_name.upper().startswith("PAGE"):
                    tests.append({
                        "test_name": t_name,
                        "result_value": m_gen.group(2).strip(),
                        "unit": m_gen.group(3).strip() if m_gen.group(3) else "",
                        "reference_range": "",
                        "status": "NORMAL"
                    })

        return {
            "document_type": document_type,
            "patient_name": patient_name,
            "report_date": report_date,
            "tests": tests,
            "medications": [],
            "impression": f"Extracted {len(tests)} test parameters from medical report.",
            "raw_snippet": raw_text[:300]
        }


# ── 3. Unified Document Pipeline ──────────────────────────────────────────────

class DocumentProcessingPipeline:
    @staticmethod
    def process_upload(
        file_bytes: bytes,
        filename: str,
        patient_id: str,
        visit_id: Optional[str],
        document_type: str
    ) -> Dict[str, Any]:
        """Main end-to-end document processing entry point."""
        doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        # Step 1: Run real OCR
        if ext == "pdf":
            ocr_res = DocumentOCRProvider.extract_from_pdf(file_bytes, filename)
        else:
            ocr_res = DocumentOCRProvider.extract_from_image(file_bytes, filename)

        # Step 2: Extract structured parameters via Groq AI
        structured = StructuredDataExtractor.extract_structured_data(ocr_res.text, document_type)

        return {
            "document_id": doc_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "document_type": document_type,
            "document_date": datetime.date.today().isoformat(),
            "raw_text": ocr_res.text,
            "ocr_confidence": ocr_res.confidence,
            "structured_data": structured,
            "verified": False
        }
