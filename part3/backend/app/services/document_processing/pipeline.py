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
        
    return variants


class DocumentOCRProvider:
    @staticmethod
    def extract_from_image(image_bytes: bytes, filename: str) -> OCRResult:
        """Extract high-accuracy text from image using Tesseract OCR (Primary) with fallback to Groq Vision / EasyOCR."""
        
        # ── 1. PRIMARY: Tesseract OCR (v5.4.0) ─────────────────────────────
        if HAS_TESSERACT:
            possible_paths = [
                getattr(settings, "TESSERACT_CMD", ""),
                os.getenv("TESSERACT_CMD", ""),
                r"C:\Users\saian\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Users\saian\AppData\Local\Tesseract-OCR\tesseract.exe"
            ]
            for p in possible_paths:
                if p and os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

            try:
                raw_img = Image.open(io.BytesIO(image_bytes))
                preprocessed_variants = preprocess_image_for_tesseract(raw_img)
                
                best_text = ""
                best_conf = 0.85
                
                # Test multiple configurations and preprocessed variants
                configs = [r"--oem 3 --psm 6", r"--oem 3 --psm 3", r"--oem 3 --psm 4"]
                
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
                    if len(best_text) > 30:
                        break

                if best_text and len(best_text.strip()) > 10:
                    logger.info(f"✅ Tesseract OCR extracted {len(best_text)} chars from {filename} (conf: {round(best_conf, 3)})")
                    return OCRResult(text=best_text, confidence=round(best_conf, 3))
            except Exception as e:
                logger.warning(f"Tesseract OCR failed ({e}), falling back to Groq Vision...")

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
                                                "text": "Transcribe and extract ALL text from this medical document image verbatim."
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
                                logger.info(f"Groq Vision ({v_model}) fallback transcribed {len(content)} chars from {filename}")
                                return OCRResult(text=content, confidence=0.98)
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
            text=f"Uploaded Document: {filename}\n[Image text could not be clearly resolved. Please ensure the image is well-lit and in focus.]",
            confidence=0.50
        )

    @staticmethod
    def extract_from_pdf(pdf_bytes: bytes, filename: str) -> OCRResult:
        """Extract real text from a PDF file using pypdf."""
        if HAS_PYPDF:
            try:
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                all_text = []
                for page_idx, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        all_text.append(page_text.strip())
                if all_text:
                    full_text = "\n\n--- Page Break ---\n\n".join(all_text)
                    logger.info(f"pypdf extracted {len(full_text)} chars across {len(reader.pages)} pages from {filename}")
                    return OCRResult(text=full_text, confidence=0.98)
            except Exception as e:
                logger.warning(f"pypdf extraction error on {filename}: {e}")

        return DocumentOCRProvider.extract_from_image(pdf_bytes, filename)


# ── 2. Structured Data Extractor via Groq AI ─────────────────────────────────

class StructuredDataExtractor:
    @staticmethod
    def extract_structured_data(raw_text: str, document_type: str) -> Dict[str, Any]:
        """Convert extracted real OCR text into structured JSON parameters via Groq AI."""
        if not raw_text or len(raw_text.strip()) < 10:
            return {"document_type": document_type, "note": "No text extracted from document"}

        prompt = f"""You are a clinical document information extraction engine.
DOCUMENT TYPE: {document_type}
RAW OCR EXTRACTED TEXT:
\"\"\"
{raw_text[:3000]}
\"\"\"

CRITICAL INSTRUCTIONS:
1. Extract ONLY facts that appear in the raw text above. Do NOT make up numbers or medicines.
2. If it's a LAB_REPORT (CBC, LFT, KFT, Blood Test), extract a "tests" array with objects:
   [{{"test_name": "...", "result_value": "...", "unit": "...", "reference_range": "...", "status": "HIGH/LOW/NORMAL"}}]
3. If it's a PRESCRIPTION, extract a "medications" array with objects:
   [{{"medicine_name": "...", "dose": "...", "frequency": "...", "duration": "...", "instructions": "..."}}]
4. Include any patient name, doctor name, test date, or impression found.

Return ONLY valid JSON matching this schema:
{{
  "document_type": "{document_type}",
  "patient_name": "...",
  "report_date": "...",
  "tests": [...],
  "medications": [...],
  "impression": "..."
}}
"""
        messages = [
            {"role": "system", "content": "You are a clinical parameter extractor. Return structured JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            resp_str = grok_service._call_groq_api(messages)
            s_idx = resp_str.find("{")
            e_idx = resp_str.rfind("}") + 1
            if s_idx != -1 and e_idx != -1:
                return json.loads(resp_str[s_idx:e_idx])
        except Exception as e:
            logger.warning(f"Groq parameter extraction failed ({e}), using heuristic parser.")

        # Heuristic fallback for lab parameters
        tests = []
        for line in raw_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Look for "Test: Value Unit"
            match = re.search(r"([A-Za-z\s\-\(\)]+?)[\:\=]\s*([0-9\.\,]+)\s*([a-zA-Z\/\%\<\>]+)?", line)
            if match:
                tests.append({
                    "test_name": match.group(1).strip(),
                    "result_value": match.group(2).strip(),
                    "unit": match.group(3).strip() if match.group(3) else "",
                    "status": "NORMAL"
                })

        return {
            "document_type": document_type,
            "tests": tests,
            "raw_snippet": raw_text[:200]
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
