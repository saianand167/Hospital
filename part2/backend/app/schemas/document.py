from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Any, Optional

# Patient Schemas
class PatientBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None # YYYY-MM-DD
    gender: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Visit Schemas
class VisitBase(BaseModel):
    patient_id: str
    doctor_name: Optional[str] = None
    visit_date: str # YYYY-MM-DD
    reason: Optional[str] = None

class VisitCreate(VisitBase):
    pass

class VisitResponse(VisitBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# Verification Schemas
class VerificationRequest(BaseModel):
    verified_by: str
    corrected_data: Dict[str, Any]

# Document Page Schema
class DocumentPageResponse(BaseModel):
    id: str
    page_number: int
    image_path: str
    width: Optional[int] = None
    height: Optional[int] = None

    class Config:
        from_attributes = True

# OCR Word Schema (per-word/line details)
class OCRWordResponse(BaseModel):
    id: str
    page_number: int
    text: str
    confidence: float
    bbox: Optional[List[float]] = None

    class Config:
        from_attributes = True

# Document Schemas
class DocumentResponse(BaseModel):
    id: str
    patient_id: str
    visit_id: Optional[str] = None
    file_name: str
    mime_type: str
    document_type: str
    document_date: Optional[str] = None
    upload_date: datetime
    quality_score: float
    ocr_status: str
    extraction_status: str
    verification_status: str
    overall_confidence: float
    structured_data: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Search RAG Schemas
class SearchQueryRequest(BaseModel):
    patient_id: str
    query: str
    top_k: Optional[int] = 5

class SearchChunkResponse(BaseModel):
    document_id: str
    document_type: str
    document_date: Optional[str] = None
    page_number: int
    section_name: Optional[str] = None
    text_content: str
    score: float

class SearchQueryResponse(BaseModel):
    query: str
    patient_id: str
    results: List[SearchChunkResponse]

# Timeline Schema
class TimelineItem(BaseModel):
    document_id: str
    document_date: Optional[str]
    upload_date: datetime
    document_type: str
    file_name: str
    verification_status: str
    overall_confidence: float
    summary: Optional[str] = None

class PatientTimelineResponse(BaseModel):
    patient_id: str
    timeline: List[TimelineItem]
