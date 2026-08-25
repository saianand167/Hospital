from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.triage import TriageResult

class ChiefComplaint(BaseModel):
    text: Optional[str] = None
    canonical: Optional[str] = None

class HPIState(BaseModel):
    duration_days: Optional[float] = None
    location: Optional[str] = None
    severity: Optional[int] = None
    character: Optional[str] = None
    radiation: Optional[str] = None
    aggravating_factors: List[str] = Field(default_factory=list)
    relieving_factors: List[str] = Field(default_factory=list)
    breathlessness: Optional[bool] = None
    sweating: Optional[bool] = None
    nausea: Optional[bool] = None
    dizziness: Optional[bool] = None
    fever: Optional[bool] = None
    cough: Optional[bool] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)

class ClinicalMetadata(BaseModel):
    completed: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    engine_version: str = "1.0"
    answered_fields: List[str] = Field(default_factory=list)

class ClinicalHistoryJSON(BaseModel):
    patient_id: str
    visit_id: str
    language: str
    chief_complaint: ChiefComplaint = Field(default_factory=ChiefComplaint)
    hpi: HPIState = Field(default_factory=HPIState)
    past_history: List[str] = Field(default_factory=list)
    past_surgical_history: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    family_history: List[str] = Field(default_factory=list)
    personal_history: Dict[str, Any] = Field(default_factory=dict)
    review_of_systems: Dict[str, Any] = Field(default_factory=dict)
    triage: TriageResult = Field(default_factory=TriageResult)
    metadata: ClinicalMetadata = Field(default_factory=ClinicalMetadata)
