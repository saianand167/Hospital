from datetime import datetime
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

InputMode = Literal["text", "voice", "touch"]

class AnswerRecord(BaseModel):
    answer_id: str
    visit_id: str
    question_id: Optional[str] = None
    user_id: str
    question_text: str
    answer_text: str
    input_mode: InputMode = "text"
    language: str = "en"
    structured_data: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
