"""
Pydantic schemas for Part 2 — Medical Document Intelligence.
These define the Part 2 -> Part 3 output contract.
"""
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from enum import Enum


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    LAB_REPORT = "LAB_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    IMAGING_REPORT = "IMAGING_REPORT"
    PATHOLOGY_REPORT = "PATHOLOGY_REPORT"
    OPD_NOTE = "OPD_NOTE"
    OTHER_MEDICAL_DOCUMENT = "OTHER_MEDICAL_DOCUMENT"
    UNKNOWN = "UNKNOWN"


# ─── Per-type data models ─────────────────────────────────────────────────────

class MedicationItem(BaseModel):
    name: Optional[str] = None
    strength: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    confidence: float = 0.0
    needs_verification: bool = False


class LabTestItem(BaseModel):
    """A single test result — value must come from OCR, never from LLM invention."""
    name: str
    value: Optional[Any] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    abnormal: Optional[bool] = None   # None = no reference range provided
    confidence: float = 0.95


class LabSection(BaseModel):
    """A named panel/section of a lab report (e.g. CBC, Renal Panel)."""
    section_name: str
    specimen: Optional[str] = None
    tests: List[LabTestItem] = []


# ─── Envelope models ─────────────────────────────────────────────────────────

class ConfidenceModel(BaseModel):
    ocr: float = 0.0
    classification: float = 0.0
    extraction: float = 0.0


class OCRPage(BaseModel):
    page: int
    text: str
    confidence: float = 0.0


class OCRResult(BaseModel):
    raw_text: str = ""
    pages: List[OCRPage] = []
    language: str = "eng"


class ClassificationResult(BaseModel):
    document_type: DocumentType
    confidence: float
    requires_verification: bool = False


class ExtractionResult(BaseModel):
    status: str = "pending"   # success | failed | partial | verification_required
    confidence: float = 0.0
    message: Optional[str] = None


class VerificationInfo(BaseModel):
    required: bool = False
    verified: bool = False
    verified_by: Optional[str] = None
    corrected_data: Optional[Dict[str, Any]] = None


class DocumentMetadata(BaseModel):
    document_date: Optional[str] = None
    source: str = "patient_upload"
    hospital_name: Optional[str] = None
    laboratory_name: Optional[str] = None
    doctor_name: Optional[str] = None
    language: str = "eng"


class StructuredDocument(BaseModel):
    """
    Part 2 -> Part 3 output contract.
    The 'data' field is flexible per document_type (JSONB-ready).
    """
    document_id: str
    patient_id: Optional[str] = None
    visit_id: Optional[str] = None
    document_type: DocumentType

    metadata: DocumentMetadata
    ocr: OCRResult
    classification: ClassificationResult
    extraction: ExtractionResult
    confidence: ConfidenceModel

    # Flexible JSONB-ready data — structure depends on document_type
    data: Dict[str, Any] = {}

    verification: VerificationInfo
    upload_timestamp: str
    file_name: str
    file_path: Optional[str] = None   # path to original preserved file


class VerifyRequest(BaseModel):
    corrected_data: Dict[str, Any]
    verified_by: str = "staff"
