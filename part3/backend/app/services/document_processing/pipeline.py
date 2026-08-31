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
    import pymupdf  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

from app.config import settings
from app.services.llm_service import grok_service

# ── Tesseract Path Detection & Setup ──────────────────────────────────────────
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

# Global EasyOCR reader cache (lazy loaded fallback)
_easyocr_reader = None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None and HAS_EASYOCR:
        try:
            logger.info("Initializing EasyOCR reader (CPU fallback)...")
            _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e:
            logger.warning(f"Could not initialize EasyOCR: {e}")
    return _easyocr_reader


# ── 1. OCR Provider & Preprocessing ───────────────────────────────────────────

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
    
    # Variant 2: Normal Grayscale with moderate contrast boost
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
        
        # ── PRIMARY: Tesseract OCR ─────────────────────────────────────────
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

        # ── FALLBACK 1: Groq Vision AI ─────────────────────────────────────
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

        # ── FALLBACK 2: EasyOCR (Python CPU) ───────────────────────────────
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

        # ── Unresolvable Image ─────────────────────────────────────────────
        return OCRResult(
            text=f"Uploaded Document: {filename}\n[Image text could not be clearly resolved.]",
            confidence=0.50
        )

    @staticmethod
    def extract_from_pdf(pdf_bytes: bytes, filename: str) -> OCRResult:
        """Extract text from all pages of PDF: selectable text or high-res page rendering for Tesseract OCR."""
        all_pages_text = []
        avg_confs = []

        # ── PyMuPDF (fitz) page rendering & OCR ────────────────────────────
        if HAS_PYMUPDF:
            try:
                doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                logger.info(f"Processing PDF '{filename}' with {len(doc)} pages using PyMuPDF + Tesseract...")
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    # Check if selectable digital text is present
                    page_text = page.get_text().strip()
                    
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

        # ── pypdf text extraction ──────────────────────────────────────────
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


# ── 2. Deterministic Medical Validator & Correction Engine ───────────────────

class DeterministicMedicalValidator:
    """
    Deterministic post-extraction validation and error correction layer.
    Ensures research citations, DOI, PMID, formulas, and equipment notes NEVER become patient test results.
    """

    NON_TEST_PATTERNS = [
        (r"\bdoi\b|10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", "DOI academic identifier, not a patient test"),
        (r"\bpmid\b|\bpubmed\b", "PubMed ID citation, not a patient test"),
        (r"evaluation of the new|beckman coulter|coulter access", "Analyzer/instrument validation reference"),
        (r"99th percentile", "Statistical reference limit description, not patient result"),
        (r"biomarker study group|esc guidelines|wallach\'s interpretation|clinical chemistry|elsevier|teitz text book", "Academic journal/guideline citation"),
        (r"ckd-epi 2009|derivation of ckd-epi|normalized to 1\.73", "eGFR formula explanation / educational disclaimer"),
        (r"system generated e-copy|authorized signatory|department of laboratory", "Laboratory legal footer/metadata"),
        (r"^page \d+ of \d+$|^end of report$", "Document pagination header/footer"),
        (r"^methodology\s*:|^specimen\s*:", "Testing methodology or specimen label"),
        (r"^note\s*:|^disclaimer\s*:", "Educational note / disclaimer"),
        (r"upper reference limit|repeat sample after|diagnostic of mi|may be ruled in", "Clinical interpretation note"),
    ]

    OCR_SPELLING_CORRECTIONS = {
        r"^roponin-i\b": "Troponin-I",
        r"^ropnin-i\b": "Troponin-I",
        r"\b(haemoglobi|hemoglobi)\b": "Haemoglobin",
        r"\b(platele|platelet count)\b": "Platelet Count",
        r"\b(creatinin)\b": "Creatinine",
        r"\b(leukocyt)\b": "Leukocyte",
        r"\b(eosinophi)\b": "Eosinophil",
        r"\b(basophi)\b": "Basophil",
        r"\b(neutrophi)\b": "Neutrophil",
        r"\b(lymphocyt)\b": "Lymphocyte",
        r"\b(monocyt)\b": "Monocyte",
    }

    UNIT_NORMALIZATIONS = {
        "mg/dl": "mg/dL",
        "mg/dl.": "mg/dL",
        "mg/100ml": "mg/dL",
        "mmol/1": "mmol/L",
        "mmol/l": "mmol/L",
        "umol/l": "µmol/L",
        "gh": "g/dL",
        "g/dl": "g/dL",
        "g/dl.": "g/dL",
        "f1": "fL",
        "fl": "fL",
        "l": "fL",
        "ul": "µL",
        "pg": "pg",
        "%": "%",
        "ng/l": "ng/L",
        "ng/ml": "ng/mL",
        "/cumm": "/cu.mm",
        "/cu mm": "/cu.mm",
        "/ cu.mm": "/cu.mm",
        "/cu.mm": "/cu.mm",
        "million/cu.mm": "million/cu.mm",
        "mil/cumm": "million/cu.mm",
        "ml/min/1.73sq.m": "ml/min/1.73sq.m",
    }

    @classmethod
    def is_non_test(cls, test_name: str, result_val: str = "") -> Tuple[bool, str]:
        """Check if item matches any research reference, DOI, PMID, or disclaimer pattern."""
        combined = f"{test_name} {result_val}".strip()
        if not test_name or len(test_name.strip()) < 2:
            return True, "Empty or invalid test name"

        for pattern, reason in cls.NON_TEST_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return True, reason
        return False, ""

    @classmethod
    def correct_test_name(cls, test_name: str) -> str:
        """Correct only unambiguous OCR character drops without hallucinating new tests."""
        cleaned = test_name.strip(" -:=#*")
        if re.search(r"^roponin-i\b", cleaned, re.IGNORECASE):
            return "Troponin-I" + cleaned[9:]
        for pat, replacement in cls.OCR_SPELLING_CORRECTIONS.items():
            if re.search(pat, cleaned, re.IGNORECASE):
                cleaned = re.sub(pat, replacement, cleaned, flags=re.IGNORECASE)
        return cleaned

    @classmethod
    def normalize_unit(cls, unit: str) -> str:
        """Normalize unit formatting."""
        u = unit.strip(" {}[]()")
        u_low = u.lower()
        if "ml/min" in u_low:
            return "ml/min/1.73sq.m"
        return cls.UNIT_NORMALIZATIONS.get(u_low, u)

    @classmethod
    def compute_status_and_flag(cls, val_str: str, ref_range: str, explicit_flag: str = "") -> Tuple[str, str]:
        """Determine clinical status ('LOW', 'NORMAL', 'HIGH', 'CRITICAL', 'ABNORMAL', 'UNKNOWN') and preserve flags."""
        flag = explicit_flag.strip()
        status = "UNKNOWN"

        # Check explicit flag first
        if flag in ("#", "*", "H", "High", "HIGH"):
            status = "HIGH" if "H" in flag.upper() else "ABNORMAL"
        elif flag in ("L", "Low", "LOW"):
            status = "LOW"
        elif "CRITICAL" in flag.upper():
            status = "CRITICAL"

        # Evaluate against numeric reference ranges if available
        if ref_range and ref_range.strip():
            try:
                v_clean = re.search(r"[-+]?\d*\.\d+|\d+", str(val_str))
                if v_clean:
                    num_val = float(v_clean.group(0))
                    
                    if "-" in ref_range:
                        parts = ref_range.split("-")
                        low_m = re.search(r"[-+]?\d*\.\d+|\d+", parts[0])
                        high_m = re.search(r"[-+]?\d*\.\d+|\d+", parts[1])
                        if low_m and high_m:
                            low_b = float(low_m.group(0))
                            high_b = float(high_m.group(0))
                            if num_val < low_b:
                                status = "LOW"
                                if not flag: flag = "#"
                            elif num_val > high_b:
                                status = "HIGH"
                                if not flag: flag = "#"
                            else:
                                status = "NORMAL"
                    elif "<" in ref_range:
                        high_m = re.search(r"[-+]?\d*\.\d+|\d+", ref_range)
                        if high_m:
                            high_b = float(high_m.group(0))
                            if num_val > high_b:
                                status = "HIGH"
                                if not flag: flag = "#"
                            else:
                                status = "NORMAL"
                    elif ">" in ref_range:
                        low_m = re.search(r"[-+]?\d*\.\d+|\d+", ref_range)
                        if low_m:
                            low_b = float(low_m.group(0))
                            if num_val < low_b:
                                status = "LOW"
                                if not flag: flag = "#"
                            else:
                                status = "NORMAL"
            except Exception:
                pass
        elif status == "UNKNOWN" and not flag:
            status = "UNKNOWN"

        return status, flag

    @classmethod
    def clean_patient_metadata(cls, patient_raw: Dict[str, Any], full_ocr_text: str = "") -> Dict[str, str]:
        """Ensure patient labels like 'Age', 'Sex', 'Reg No' are cleanly separated from patient_name."""
        cleaned = {
            "patient_name": "",
            "age": "",
            "sex": "",
            "registration_no": "",
            "lab_no": "",
            "patient_episode": "",
            "collection_date": "",
            "receiving_date": "",
            "reporting_date": "",
            "referred_by": "",
            "specimen": ""
        }
        
        # Populate from provided dictionary
        for k in cleaned.keys():
            v = str(patient_raw.get(k, "") or "").strip()
            if k == "patient_name" and v:
                v = re.split(r"\b(Age|Sex|Reg|Registration|Lab|Date|Episode|Ref|Dr)\b", v, flags=re.IGNORECASE)[0]
                v = v.strip(" :-\t\n")
                if any(kw in v.upper() for kw in ["HOSPITAL", "DOCTOR", "LABORATORY", "PAGE", "REPORT", "CERTIFICATE"]):
                    v = ""
            cleaned[k] = v

        # Fallback to scanning OCR text directly if metadata is missing
        if full_ocr_text and not cleaned["patient_name"]:
            for line in full_ocr_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "NAME" in line.upper() and ("AGE" in line.upper() or "SEX" in line.upper() or ":" in line):
                    m_n = re.search(r"Name\s*[:\-=]\s*([A-Za-z\s\.\,\'\-]+?)(?=\s+(?:Age|Sex|Reg|Lab|Date|Episode|Ref|Dr|$))", line, re.IGNORECASE)
                    if m_n and not cleaned["patient_name"]:
                        n_cand = m_n.group(1).strip(" :-\t")
                        if len(n_cand) > 1 and not any(kw in n_cand.upper() for kw in ["HOSPITAL", "DOCTOR", "LABORATORY", "PAGE", "REPORT", "CERTIFICATE"]):
                            cleaned["patient_name"] = n_cand
                    
                    m_a = re.search(r"Age\s*[:\-=]\s*([0-9]{1,3}(?:\s*(?:yrs|years|y|m|months))?|[A-Za-z]{1,4})", line, re.IGNORECASE)
                    if m_a and not cleaned["age"]:
                        cleaned["age"] = m_a.group(1).strip()
                        
                    m_s = re.search(r"Sex\s*[:\-=]\s*([A-Za-z]+)", line, re.IGNORECASE)
                    if m_s and not cleaned["sex"]:
                        cleaned["sex"] = m_s.group(1).strip()

                if "REGISTRATION" in line.upper() or "LAB NO" in line.upper():
                    m_reg = re.search(r"Registration\s*No\s*[:\-=]?\s*([A-Za-z0-9\-_]+)", line, re.IGNORECASE)
                    if m_reg and not cleaned["registration_no"]:
                        cleaned["registration_no"] = m_reg.group(1).strip()
                    m_lab = re.search(r"Lab\s*No\s*[:\-=]?\s*([A-Za-z0-9\-_]+)", line, re.IGNORECASE)
                    if m_lab and not cleaned["lab_no"]:
                        cleaned["lab_no"] = m_lab.group(1).strip()

                if "SPECIMEN" in line.upper():
                    m_spec = re.search(r"Specimen\s*[:\-=]?\s*([A-Za-z0-9\s\/\-_]+)", line, re.IGNORECASE)
                    if m_spec and not cleaned["specimen"]:
                        cleaned["specimen"] = m_spec.group(1).strip()

        return cleaned

    @classmethod
    def validate_and_normalize(cls, raw_data: Dict[str, Any], full_ocr_text: str = "") -> Dict[str, Any]:
        """
        Comprehensive deterministic validation pass:
        1. Separates genuine tests from excluded non-test items (DOI, PMID, research citations).
        2. Corrects unambiguous OCR errors and normalizes units.
        3. Computes accurate clinical status and preserves flags.
        4. Detects and recovers missing tests from full multi-page OCR text.
        5. Calculates exact validation metrics dynamically.
        """
        patient = cls.clean_patient_metadata(raw_data.get("patient", {}), full_ocr_text=full_ocr_text)
        raw_tests = raw_data.get("tests", [])
        raw_excluded = raw_data.get("excluded_items", [])

        valid_tests: List[Dict[str, Any]] = []
        excluded_items: List[Dict[str, Any]] = []

        # Preserve previously identified excluded items
        for ex in raw_excluded:
            if isinstance(ex, dict) and ex.get("text"):
                excluded_items.append({"text": str(ex["text"]).strip(), "reason": str(ex.get("reason", "Excluded item")).strip()})

        # Process each extracted test candidate
        for t in raw_tests:
            if not isinstance(t, dict):
                continue

            t_name = str(t.get("test_name", "")).strip()
            r_val = str(t.get("result_value", "")).strip()

            # Check if this item is actually a reference citation / DOI / PMID / disclaimer
            is_bad, reason = cls.is_non_test(t_name, r_val)
            if is_bad:
                excluded_items.append({"text": f"{t_name}: {r_val}".strip(" :"), "reason": reason})
                continue

            # Check if result_value contains numbers or valid clinical text
            if not r_val or r_val.lower() in ("null", "none", "n/a"):
                excluded_items.append({"text": t_name, "reason": "No patient measurement result"})
                continue

            corrected_name = cls.correct_test_name(t_name)
            unit_norm = cls.normalize_unit(str(t.get("unit", "")))
            ref_r = str(t.get("reference_range", "")).strip(" []{}()")
            expl_flag = str(t.get("flag", "")).strip()

            # Calculate accurate clinical status and explicit flag
            status, flag = cls.compute_status_and_flag(r_val, ref_r, expl_flag)

            # Confidence assessment
            conf = str(t.get("confidence", "HIGH")).upper()
            if conf not in ("HIGH", "MEDIUM", "LOW"):
                conf = "HIGH"

            section = str(t.get("section", "")).strip()
            if not section and "TROPONIN" in corrected_name.upper():
                section = "BIOCHEMISTRY / CARDIAC MARKERS"

            valid_tests.append({
                "section": section,
                "test_name": corrected_name,
                "result_value": r_val,
                "unit": unit_norm,
                "reference_range": ref_r,
                "status": status,
                "flag": flag,
                "confidence": conf
            })

        # ── Second-Pass Full Document Parser & Missing Test Recovery ────────
        possible_missing = False
        if full_ocr_text:
            extracted_names_clean = {re.sub(r"[^a-zA-Z0-9]", "", t["test_name"].lower()) for t in valid_tests}
            curr_section = "BIOCHEMISTRY"
            
            for line in full_ocr_text.split("\n"):
                line = line.strip()
                if not line or line.startswith("--- Page") or line.startswith("LIFE"):
                    continue

                # Section tracking
                if "RENAL PANEL" in line.upper():
                    curr_section = "RENAL PANEL - I"
                    continue
                elif "TROPONIN" in line.upper() and ("HIGH SENSITIVE" in line.upper() or "CARDIAC" in line.upper()):
                    curr_section = "BIOCHEMISTRY / CARDIAC MARKERS"
                    continue
                elif "COMPLETE BLOOD COUNT" in line.upper():
                    curr_section = "HAEMATOLOGY / COMPLETE BLOOD COUNT"
                    continue
                elif "DIFFERENTIAL COUNT" in line.upper():
                    curr_section = "HAEMATOLOGY / DIFFERENTIAL COUNT"
                    continue

                # Check non-test patterns
                is_bad, reason = cls.is_non_test(line)
                if is_bad:
                    if not any(ex["text"] == line for ex in excluded_items):
                        excluded_items.append({"text": line, "reason": reason})
                    continue

                # Match tabular lab rows across all bracket formats and flag styles
                m_tab = re.search(
                    r"^([A-Za-z0-9\s\-\(\)\/\*\.\,\:]+?)\s+([0-9\.]+)\s*(#|\*)?\s+([a-zA-Z\/\%\<\>\.\-\^0-9]+|\/\s*cu\.?mm|\/cu\s*mm)\s+(?:\[|\{|\{\[|\{\()?([0-9\.\-\<\>\s]{2,20})(?:\]|\)|\}\])?",
                    line
                )
                if m_tab:
                    cand_name = cls.correct_test_name(m_tab.group(1).strip(" *#-:= "))
                    is_bad, reason = cls.is_non_test(cand_name, m_tab.group(2))
                    if is_bad:
                        if not any(ex["text"] == line for ex in excluded_items):
                            excluded_items.append({"text": line, "reason": reason})
                        continue

                    cand_clean = re.sub(r"[^a-zA-Z0-9]", "", cand_name.lower())
                    if cand_clean and cand_clean not in extracted_names_clean:
                        rec_val = m_tab.group(2).strip()
                        rec_flag = m_tab.group(3).strip() if m_tab.group(3) else ""
                        rec_unit = cls.normalize_unit(m_tab.group(4))
                        rec_ref = m_tab.group(5).strip(" []{}()")
                        rec_status, rec_flag = cls.compute_status_and_flag(rec_val, rec_ref, rec_flag)
                        
                        sec = curr_section
                        if "TROPONIN" in cand_name.upper():
                            sec = "BIOCHEMISTRY / CARDIAC MARKERS"

                        valid_tests.append({
                            "section": sec,
                            "test_name": cand_name,
                            "result_value": rec_val,
                            "unit": rec_unit,
                            "reference_range": rec_ref,
                            "status": rec_status,
                            "flag": rec_flag,
                            "confidence": "HIGH"
                        })
                        extracted_names_clean.add(cand_clean)

        # ── Dynamic Calculation of All Validation Counts ──────────────────
        high_c = sum(1 for t in valid_tests if t["confidence"] == "HIGH")
        med_c = sum(1 for t in valid_tests if t["confidence"] == "MEDIUM")
        low_c = sum(1 for t in valid_tests if t["confidence"] == "LOW")

        return {
            "document_type": raw_data.get("document_type", "LAB_REPORT"),
            "patient": patient,
            "tests": valid_tests,
            "medications": raw_data.get("medications", []),
            "excluded_items": excluded_items,
            "validation": {
                "total_tests": len(valid_tests),
                "high_confidence_tests": high_c,
                "medium_confidence_tests": med_c,
                "low_confidence_tests": low_c,
                "excluded_non_test_items": len(excluded_items),
                "possible_missing_tests": possible_missing,
                "notes": f"Validated {len(valid_tests)} patient laboratory tests. Filtered {len(excluded_items)} non-test items."
            }
        }


# ── 3. Structured Data Extractor via Groq AI ─────────────────────────────────

class StructuredDataExtractor:
    @staticmethod
    def extract_structured_data(raw_text: str, document_type: str) -> Dict[str, Any]:
        """Convert complete OCR text into validated structured JSON parameters via Groq AI."""
        if not raw_text or len(raw_text.strip()) < 10:
            return DeterministicMedicalValidator.validate_and_normalize(
                {"document_type": document_type, "tests": [], "excluded_items": []},
                full_ocr_text=""
            )

        prompt = f"""You are an expert medical laboratory report OCR extraction and validation engine.

Your task is to convert the COMPLETE OCR TEXT provided at the bottom of this prompt into accurate, structured JSON.

IMPORTANT:
1. Extract information from ALL pages of the OCR TEXT across all laboratory sections.
2. Accuracy is paramount. Extract ONLY genuine PATIENT LABORATORY TEST RESULTS.
   A genuine test result normally contains: TEST NAME + PATIENT RESULT + UNIT and/or REFERENCE RANGE.
3. NEVER EXTRACT THESE AS TESTS (place them in excluded_items instead):
   - DOI, PMID, journal citations, bibliography, research papers, study authors, publication information
   - Methodology descriptions, analyzer/instrument descriptions, educational text, disclaimers, comments, notes
   - 99th percentile text unless explicitly the patient's individual measurement
   - Isolated numbers, dates, registration numbers, page headers/footers
4. OCR Error Correction:
   - Correct only obvious OCR spelling errors in medical names (e.g. 'roponin-I' -> 'Troponin-I').
   - Normalize unit formatting ('mg/dl' -> 'mg/dL', 'mmol/1' -> 'mmol/L', '/cu mm' -> '/cu.mm').
   - Preserve exact reported numeric precision (e.g. '1.30' -> '1.30', '9.81' -> '9.81', '115.5' -> '115.5').
5. Preserve actual test names (e.g. 'Plasma GLUCOSE- Random (Hexokinase)', 'BUN (Urease/GLDH)').
6. Determine status ('LOW', 'NORMAL', 'HIGH', 'CRITICAL', 'ABNORMAL', 'UNKNOWN') from the report's printed reference range and explicit flags. Do not mark every test NORMAL.
7. Preserve explicit abnormality flags (e.g. '#', '*', 'H', 'L') in the 'flag' field.
8. Extract patient metadata separately without combining field labels (e.g. 'Name : Ria' -> patient_name='Ria', age='').
9. Return ONLY valid, parseable JSON matching the exact schema below.

SCHEMA:
{{
  "document_type": "{document_type}",
  "patient": {{
    "patient_name": "",
    "age": "",
    "sex": "",
    "registration_no": "",
    "lab_no": "",
    "patient_episode": "",
    "collection_date": "",
    "receiving_date": "",
    "reporting_date": "",
    "referred_by": "",
    "specimen": ""
  }},
  "tests": [
    {{
      "section": "",
      "test_name": "",
      "result_value": "",
      "unit": "",
      "reference_range": "",
      "status": "",
      "flag": "",
      "confidence": "HIGH"
    }}
  ],
  "medications": [],
  "excluded_items": [
    {{
      "text": "",
      "reason": ""
    }}
  ],
  "validation": {{
    "total_tests": 0,
    "high_confidence_tests": 0,
    "medium_confidence_tests": 0,
    "low_confidence_tests": 0,
    "excluded_non_test_items": 0,
    "possible_missing_tests": false,
    "notes": ""
  }}
}}

<START_OCR>
{raw_text[:12000]}
<END_OCR>
"""
        messages = [
            {"role": "system", "content": "You are a clinical laboratory OCR validation and structured data extraction engine. Return ONLY the JSON object."},
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
                if isinstance(parsed, dict) and "tests" in parsed:
                    # Run deterministic validation pass on LLM output
                    validated = DeterministicMedicalValidator.validate_and_normalize(parsed, full_ocr_text=raw_text)
                    return validated
        except Exception as e:
            logger.warning(f"Groq parameter extraction failed ({e}), using deterministic candidate extractor.")

        # Fallback candidate extractor if LLM is unavailable
        candidate_data = {
            "document_type": document_type,
            "patient": {},
            "tests": [],
            "medications": [],
            "excluded_items": []
        }
        return DeterministicMedicalValidator.validate_and_normalize(candidate_data, full_ocr_text=raw_text)


# ── 4. Unified Document Processing Pipeline ───────────────────────────────────

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

        # Step 1: Run OCR on complete multi-page document
        if ext == "pdf":
            ocr_res = DocumentOCRProvider.extract_from_pdf(file_bytes, filename)
        else:
            ocr_res = DocumentOCRProvider.extract_from_image(file_bytes, filename)

        # Step 2: Extract & validate structured parameters via LLM + Deterministic Validator
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
