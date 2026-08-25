from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

LanguageCode = Literal["en", "te", "hi"]

class PatientSession(BaseModel):
    patient_id: str = Field(default="PAT-0001", description="Patient Identifier")
    visit_id: str = Field(default="VIS-0001", description="Visit / Consultation Identifier")
    language: LanguageCode = Field(default="en", description="Selected interaction language")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_completed: bool = False
    is_escalated: bool = False
