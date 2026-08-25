from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

TriageFlag = Literal["GREEN", "YELLOW", "RED"]

class TriageResult(BaseModel):
    flag: TriageFlag = "GREEN"
    priority: bool = False
    reason_codes: List[str] = Field(default_factory=list)
    triggering_parameters: Dict[str, Any] = Field(default_factory=dict)
    evaluated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    recommendation: str = "Proceed with routine consultation."
