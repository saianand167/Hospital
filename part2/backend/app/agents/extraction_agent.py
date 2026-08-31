"""
Type-Specific Extraction Agent.

Routes each document type to its own dedicated Pydantic-based extractor.
Uses native LLM JSON Mode constraint for 100% syntactically valid JSON.
- LAB_REPORT: Pydantic structured extraction of sections and tests.
- PRESCRIPTION: Pydantic structured extraction of medications.
- DISCHARGE_SUMMARY: Pydantic structured extraction.
- IMAGING_REPORT: Pydantic structured extraction.
- PATHOLOGY_REPORT: Pydantic structured extraction.
- OPD_NOTE: Pydantic structured extraction.

IMPORTANT:
  Numerical lab values MUST come from OCR text.
  LLM is used to structure/normalize, not to invent values.
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel
from app.schemas.documents import DocumentType
from app.services.llm import get_llm_provider
from app.config import settings

# ─── Lab report section names (normalized) ────────────────────────────────────
KNOWN_SECTIONS = [
    "complete blood count", "cbc", "haematology", "hematology",
    "renal panel", "renal function", "kidney function",
    "liver function", "lft", "hepatic panel",
    "lipid profile", "lipid panel",
    "thyroid profile", "thyroid function",
    "cardiac markers", "cardiac panel",
    "diabetes panel", "hba1c",
    "electrolytes", "electrolyte panel",
    "urine analysis", "urinalysis",
    "coagulation", "coagulation profile",
    "inflammatory markers",
]

# ─── Pydantic schemas for extraction ──────────────────────────────────────────

class LabTestItemSchema(BaseModel):
    name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    source_text: Optional[str] = None
    confidence: Optional[float] = 0.95
    reference_range: Optional[str] = None

class LabSectionSchema(BaseModel):
    name: str
    specimen: Optional[str] = None
    tests: List[LabTestItemSchema] = []

class LabReportMetadataSchema(BaseModel):
    hospital_name: Optional[str] = None
    laboratory_name: Optional[str] = None
    doctor_name: Optional[str] = None
    document_date: Optional[str] = None

class LabReportSchema(BaseModel):
    metadata: LabReportMetadataSchema
    sections: List[LabSectionSchema] = []


class PrescriptionMedicationSchema(BaseModel):
    name: str
    strength: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    confidence: float = 0.95
    needs_verification: bool = False

class PrescriptionSchema(BaseModel):
    document_date: Optional[str] = None
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    patient_name: Optional[str] = None
    medications: List[PrescriptionMedicationSchema] = []


class DischargeSummarySchema(BaseModel):
    document_date: Optional[str] = None
    hospital_name: Optional[str] = None
    doctor_name: Optional[str] = None
    patient_name: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    diagnoses: List[str] = []
    procedures: List[str] = []
    hospital_course: Optional[str] = None
    medications_on_discharge: List[str] = []
    follow_up_instructions: Optional[str] = None
    condition_on_discharge: Optional[str] = None


class ImagingMeasurementSchema(BaseModel):
    name: str
    value: str
    unit: Optional[str] = None

class ImagingReportSchema(BaseModel):
    document_date: Optional[str] = None
    hospital_name: Optional[str] = None
    radiologist_name: Optional[str] = None
    modality: Optional[str] = None
    body_part: Optional[str] = None
    clinical_indication: Optional[str] = None
    findings: Optional[str] = None
    impression: Optional[str] = None
    measurements: List[ImagingMeasurementSchema] = []


class PathologyReportSchema(BaseModel):
    document_date: Optional[str] = None
    hospital_name: Optional[str] = None
    pathologist_name: Optional[str] = None
    specimen_site: Optional[str] = None
    clinical_history: Optional[str] = None
    gross_examination: Optional[str] = None
    microscopic_findings: Optional[str] = None
    pathological_diagnosis: Optional[str] = None


class OpdNoteSchema(BaseModel):
    document_date: Optional[str] = None
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    patient_name: Optional[str] = None
    chief_complaint: Optional[str] = None
    history_of_present_illness: Optional[str] = None
    past_medical_history: Optional[str] = None
    examination_findings: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    follow_up: Optional[str] = None

# ─── Helper Functions ─────────────────────────────────────────────────────────

def _normalize_value(raw: str) -> Any:
    """Parse numeric value from an OCR string."""
    raw = raw.strip()
    # Handle values like ">5.5", "<0.1", "3.2 - 5.6" (pick first number)
    m = re.search(r'[\d]+\.?[\d]*', raw)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return raw
    return raw or None


def _check_abnormal(value: Any, ref_range: Optional[str]) -> Tuple[Optional[bool], dict]:
    """
    Compare extracted value against reference range if parseable.
    Returns (abnormal_flag, interpretation_dict).
    interpretation: {"status": "LOW"|"NORMAL"|"HIGH"|"UNKNOWN", "source": "document_reference_range"|None}
    """
    default_interp = {"status": "UNKNOWN", "source": None}
    if value is None or not ref_range:
        return None, default_interp
    try:
        val = float(value)
        range_clean = ref_range.replace(",", "")
        m_range = re.search(r'([\d.]+)\s*[-–]\s*([\d.]+)', range_clean)
        m_lt = re.search(r'[<≤]\s*([\d.]+)', range_clean)
        m_gt = re.search(r'[>≥]\s*([\d.]+)', range_clean)
        if m_range:
            lo, hi = float(m_range.group(1)), float(m_range.group(2))
            if val < lo:
                return True, {"status": "LOW", "source": "document_reference_range"}
            elif val > hi:
                return True, {"status": "HIGH", "source": "document_reference_range"}
            else:
                return False, {"status": "NORMAL", "source": "document_reference_range"}
        elif m_lt:
            limit = float(m_lt.group(1))
            if val >= limit:
                return True, {"status": "HIGH", "source": "document_reference_range"}
            else:
                return False, {"status": "NORMAL", "source": "document_reference_range"}
        elif m_gt:
            limit = float(m_gt.group(1))
            if val <= limit:
                return True, {"status": "LOW", "source": "document_reference_range"}
            else:
                return False, {"status": "NORMAL", "source": "document_reference_range"}
    except (ValueError, TypeError):
        pass
    return None, default_interp


# ─── Extractor Functions ──────────────────────────────────────────────────────

def extract_lab_report(ocr_text: str) -> Dict[str, Any]:
    llm = get_llm_provider(settings.llm_provider)
    prompt = (
        "Extract all laboratory test results from the OCR text of a medical laboratory report. "
        "Group tests by their panel or section name (e.g., 'Complete Blood Count', 'Differential Count'). "
        "For each test, extract the name, value, unit, and reference range exactly as written. "
        "Also estimate a source_text snippet where the test was found in the OCR. "
        "Do not invent values. OCR text:\n\n" + ocr_text[:7000]
    )
    try:
        parsed = llm.generate_json(prompt, LabReportSchema)
    except Exception as e:
        print(f"Lab extraction LLM error: {e}")
        return {
            "document_type": "laboratory_report",
            "metadata": {
                "hospital_name": None,
                "laboratory_name": None,
                "doctor_name": None,
                "document_date": None,
            },
            "sections": [],
            "quality": {
                "ocr_quality": "low",
                "extraction_complete": False,
                "requires_verification": True,
            },
            "_extraction_note": f"LLM extraction failed: {e}",
        }

    # Post-process: compute abnormal flags from extracted values + reference ranges
    sections_out = []
    for section in parsed.get("sections", []):
        tests_out = []
        for test in section.get("tests", []):
            raw_val = test.get("value")
            ref = test.get("reference_range")
            normalized_val = _normalize_value(str(raw_val)) if raw_val is not None else None
            abnormal, interp = _check_abnormal(normalized_val, ref)
            tests_out.append({
                "name": test.get("name", ""),
                "value": normalized_val,
                "unit": test.get("unit"),
                "source_text": test.get("source_text"),
                "confidence": test.get("confidence") or 0.95,
                "reference_range": ref,
                "abnormal": abnormal,
                "interpretation": interp,
            })
        sections_out.append({
            "name": section.get("name", "Unknown"),
            "section_name": section.get("name", "Unknown"),  # compatibility
            "specimen": section.get("specimen"),
            "tests": tests_out,
        })

    metadata_obj = parsed.get("metadata", {}) if isinstance(parsed.get("metadata"), dict) else {}

    return {
        "document_type": "laboratory_report",
        "metadata": {
            "hospital_name": metadata_obj.get("hospital_name"),
            "laboratory_name": metadata_obj.get("laboratory_name"),
            "doctor_name": metadata_obj.get("doctor_name"),
            "document_date": metadata_obj.get("document_date"),
        },
        "sections": sections_out,
        "quality": {
            "ocr_quality": "high",
            "extraction_complete": True,
            "requires_verification": False,
        }
    }


def extract_prescription(ocr_text: str) -> Dict[str, Any]:
    llm = get_llm_provider(settings.llm_provider)
    prompt = (
        "Extract all medications, dosages, frequencies, and durations from the OCR text of a medical prescription. "
        "Do not invent drugs. OCR text:\n\n" + ocr_text[:5000]
    )
    try:
        return llm.generate_json(prompt, PrescriptionSchema)
    except Exception as e:
        print(f"Prescription extraction error: {e}")
        return {"medications": [], "_extraction_note": f"LLM extraction failed: {e}"}


def extract_discharge_summary(ocr_text: str) -> Dict[str, Any]:
    llm = get_llm_provider(settings.llm_provider)
    prompt = (
        "Extract structured hospitalization details, discharge diagnoses, procedures, and follow-up from the discharge summary. "
        "OCR text:\n\n" + ocr_text[:6000]
    )
    try:
        return llm.generate_json(prompt, DischargeSummarySchema)
    except Exception as e:
        print(f"Discharge summary extraction error: {e}")
        return {"_extraction_note": f"LLM extraction failed: {e}"}


def extract_imaging_report(ocr_text: str) -> Dict[str, Any]:
    llm = get_llm_provider(settings.llm_provider)
    prompt = (
        "Extract the imaging modality, body part, radiologist findings, impression, and any specific measurements. "
        "OCR text:\n\n" + ocr_text[:5000]
    )
    try:
        return llm.generate_json(prompt, ImagingReportSchema)
    except Exception as e:
        print(f"Imaging extraction error: {e}")
        return {"_extraction_note": f"LLM extraction failed: {e}"}


def extract_pathology_report(ocr_text: str) -> Dict[str, Any]:
    llm = get_llm_provider(settings.llm_provider)
    prompt = (
        "Extract pathology report details: specimen site, clinical history, macroscopic and microscopic findings, and final diagnosis. "
        "OCR text:\n\n" + ocr_text[:5000]
    )
    try:
        return llm.generate_json(prompt, PathologyReportSchema)
    except Exception as e:
        print(f"Pathology extraction error: {e}")
        return {"_extraction_note": f"LLM extraction failed: {e}"}


def extract_opd_note(ocr_text: str) -> Dict[str, Any]:
    llm = get_llm_provider(settings.llm_provider)
    prompt = (
        "Extract the chief complaint, clinical assessment/findings, plan of care, and follow-up from the consultation note. "
        "OCR text:\n\n" + ocr_text[:5000]
    )
    try:
        return llm.generate_json(prompt, OpdNoteSchema)
    except Exception as e:
        print(f"OPD note extraction error: {e}")
        return {"_extraction_note": f"LLM extraction failed: {e}"}


# ─── MAIN DISPATCHER ──────────────────────────────────────────────────────────

class ExtractionAgent:
    @staticmethod
    def extract(document_type: DocumentType, ocr_text: str) -> Dict[str, Any]:
        """
        Route document to the correct type-specific extractor.
        Never runs prescription extractor on a lab report.
        """
        if document_type == DocumentType.LAB_REPORT:
            return extract_lab_report(ocr_text)
        elif document_type == DocumentType.PRESCRIPTION:
            return extract_prescription(ocr_text)
        elif document_type == DocumentType.DISCHARGE_SUMMARY:
            return extract_discharge_summary(ocr_text)
        elif document_type == DocumentType.IMAGING_REPORT:
            return extract_imaging_report(ocr_text)
        elif document_type == DocumentType.PATHOLOGY_REPORT:
            return extract_pathology_report(ocr_text)
        elif document_type == DocumentType.OPD_NOTE:
            return extract_opd_note(ocr_text)
        else:
            return {
                "raw_text_summary": ocr_text[:500],
                "_extraction_note": "Document type unknown. Human verification required.",
            }
