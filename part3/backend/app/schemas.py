from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    full_name: Optional[str] = None
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None
    pharmacist_id: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# --- Patient Schemas ---
class PatientBase(BaseModel):
    name: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: Optional[str] = "English"

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: int
    patient_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Visit Schemas ---
class VisitBase(BaseModel):
    patient_id: str
    doctor_id: Optional[str] = None
    department: Optional[str] = "General Medicine"
    priority: Optional[str] = "NORMAL"  # NORMAL, HIGH, EMERGENCY

class VisitCreate(VisitBase):
    pass

class VisitResponse(VisitBase):
    id: int
    visit_id: str
    visit_date: datetime
    status: str  # WAITING, IN_PROGRESS, COMPLETED
    created_at: datetime

    class Config:
        from_attributes = True

class VisitStatusUpdate(BaseModel):
    status: str
    priority: Optional[str] = None

# --- Clinical History Schemas ---
class ClinicalHistoryCreate(BaseModel):
    visit_id: str
    patient_id: str
    history_json: Dict[str, Any]
    source: Optional[str] = "Part1_Engine"

class ClinicalHistoryResponse(BaseModel):
    id: int
    visit_id: str
    patient_id: str
    history_json: Dict[str, Any]
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Document Schemas ---
class DocumentCreate(BaseModel):
    patient_id: str
    visit_id: Optional[str] = None
    document_type: str  # LAB_REPORT, XRAY, PRESCRIPTION, DISCHARGE_SUMMARY
    document_date: Optional[datetime] = None
    raw_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    ocr_confidence: Optional[float] = 1.0
    extraction_confidence: Optional[float] = 1.0
    verification_required: Optional[bool] = False
    verified: Optional[bool] = True
    file_reference: Optional[str] = None

class DocumentVerifyRequest(BaseModel):
    verified: bool
    structured_data: Optional[Dict[str, Any]] = None

class DocumentResponse(BaseModel):
    id: int
    document_id: str
    patient_id: str
    visit_id: Optional[str] = None
    document_type: str
    document_date: datetime
    raw_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    ocr_confidence: float
    extraction_confidence: float
    verification_required: bool
    verified: bool
    file_reference: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- Prescription Schemas ---
class PrescriptionItemBase(BaseModel):
    medicine_name: str
    dose: str
    route: Optional[str] = "Oral"
    frequency: str  # e.g., BD, TDS, Twice daily
    duration: str   # e.g., 3 days
    instructions: Optional[str] = "After food"

class PrescriptionItemCreate(PrescriptionItemBase):
    pass

class PrescriptionItemResponse(PrescriptionItemBase):
    id: int
    prescription_id: str

    class Config:
        from_attributes = True

class VoicePrescriptionRequest(BaseModel):
    patient_id: str
    visit_id: str
    doctor_id: str
    transcript: str  # Voice dictation text

class PrescriptionCreate(BaseModel):
    patient_id: str
    visit_id: str
    doctor_id: str
    items: List[PrescriptionItemCreate]

class PrescriptionConfirmRequest(BaseModel):
    items: Optional[List[PrescriptionItemCreate]] = None

class PrescriptionResponse(BaseModel):
    id: int
    prescription_id: str
    patient_id: str
    visit_id: str
    doctor_id: str
    status: str  # DRAFT, FINAL, CANCELLED
    created_at: datetime
    items: List[PrescriptionItemResponse] = []

    class Config:
        from_attributes = True

# --- RAG & Doctor Summary Schemas ---
class DoctorSummaryResponse(BaseModel):
    patient_id: str
    visit_id: Optional[str] = None
    chief_complaint: str
    hpi: str
    relevant_past_history: str
    medications: List[str]
    allergies: List[str]
    family_personal_history: str
    relevant_previous_investigations: str
    previous_treatments: str
    current_triage_flag: str
    sources: List[Dict[str, str]]

class DoctorSummaryUpdateRequest(BaseModel):
    summary_text: str

class RAGQueryRequest(BaseModel):
    patient_id: str
    query: str

class RAGSourceItem(BaseModel):
    source_id: str
    source_type: str
    document_date: str
    snippet: str

class RAGQueryResponse(BaseModel):
    patient_id: str
    query: str
    answer: str
    grounded: bool
    sources: List[RAGSourceItem]

# --- Audit Log Schemas ---
class AuditLogResponse(BaseModel):
    id: int
    user_id: str
    action: str
    target_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# --- Patient Self-Registration Schema ---
class PatientRegisterRequest(BaseModel):
    """Used by the unified /patients/register endpoint.
    Creates both a Patient record (PAT-XXXXXX) and a User account in one
    atomic transaction. This is the single patient onboarding path across
    all three parts of the MediKiosk system.
    """
    full_name: str
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    preferred_language: Optional[str] = "English"


class PatientRegisterResponse(BaseModel):
    patient_id: str
    username: str
    full_name: str
    preferred_language: str
    access_token: str   # JWT so the user is logged in immediately after registration
    token_type: str = "bearer"
    role: str = "PATIENT"
