from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# --- PRESCRIPTION SCHEMA ---
class DoctorInfo(BaseModel):
    name: Optional[str] = None
    registration_number: Optional[str] = None

class MedicationItem(BaseModel):
    name: str = ""
    strength: Optional[str] = None
    dosage_form: Optional[str] = None  # tablet, capsule, syrup, etc.
    dose: Optional[str] = None          # 1 tab, 5ml, etc.
    route: Optional[str] = None         # oral, IV, topical, etc.
    frequency: Optional[str] = None     # 1-0-1, once daily, TDS, etc.
    duration: Optional[str] = None      # 5 days, 1 month, etc.
    timing: Optional[str] = None        # before food, after food
    instructions: Optional[str] = None  # avoid milk, take at bedtime, etc.
    confidence: float = 0.0
    verification_status: str = "unverified"

class PrescriptionExtraction(BaseModel):
    document_type: str = "prescription"
    doctor: DoctorInfo = Field(default_factory=DoctorInfo)
    date: Optional[str] = None
    medications: List[MedicationItem] = Field(default_factory=list)


# --- LAB REPORT SCHEMA ---
class ReferenceRange(BaseModel):
    low: Optional[float] = None
    high: Optional[float] = None
    text: Optional[str] = None # For non-numeric or custom ranges

class LabTestItem(BaseModel):
    name: str
    value: Optional[Any] = None # can be float, int, or string (like "Negative")
    unit: Optional[str] = None
    reference_range: Optional[ReferenceRange] = None
    status: str = "unknown" # low, high, normal, unknown
    confidence: float = 0.0

class LabReportExtraction(BaseModel):
    document_type: str = "lab_report"
    report_date: Optional[str] = None
    laboratory: Optional[str] = None
    patient_name: Optional[str] = None
    tests: List[LabTestItem] = Field(default_factory=list)


# --- RADIOLOGY REPORT SCHEMA ---
class RadiologyExtraction(BaseModel):
    document_type: str = "radiology_report"
    study_date: Optional[str] = None
    modality: Optional[str] = None       # X-Ray, CT, MRI, Ultrasound
    body_region: Optional[str] = None    # Chest, Abdomen, Brain
    findings: List[str] = Field(default_factory=list)
    impression: str = ""
    measurements: List[str] = Field(default_factory=list)
    confidence: float = 0.0


# --- DISCHARGE SUMMARY SCHEMA ---
class DischargeSummaryExtraction(BaseModel):
    document_type: str = "discharge_summary"
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    hospital: Optional[str] = None
    diagnoses: List[str] = Field(default_factory=list)
    procedures: List[str] = Field(default_factory=list)
    hospital_course: str = ""
    medications: List[Dict[str, Any]] = Field(default_factory=list) # List of medications extracted from discharge summary
    investigations: List[Dict[str, Any]] = Field(default_factory=list) # List of key lab tests mentioned
    follow_up: str = ""
    confidence: float = 0.0


# --- GENERIC / UNKNOWN SCHEMA ---
class GenericEntity(BaseModel):
    entity_type: str
    value: str
    confidence: float = 0.0

class GenericExtraction(BaseModel):
    document_type: str = "unknown"
    raw_text: str = ""
    entities: List[GenericEntity] = Field(default_factory=list)
    confidence: float = 0.0
    verification_required: bool = True
