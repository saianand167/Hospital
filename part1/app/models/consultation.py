from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

ConsultationStatus = Literal["active", "completed", "escalated"]

class ConsultationCreate(BaseModel):
    user_id: str
    language: str = "en"
    current_complaint: Optional[str] = None

class ConsultationSummary(BaseModel):
    visit_id: str
    user_id: str
    language: str
    current_complaint: Optional[str] = None
    status: str = "active"
    started_at: str
    completed_at: Optional[str] = None
    triage_flag: str = "GREEN"
    triage_priority: bool = False
