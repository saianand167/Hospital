from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

QuestionType = Literal["yes_no", "single_choice", "multiple_choice", "scale", "number", "text"]

class LocalizedText(BaseModel):
    en: str
    te: Optional[str] = None
    hi: Optional[str] = None

class OptionChoice(BaseModel):
    value: str
    label: LocalizedText

class QuestionDefinition(BaseModel):
    field_name: str
    question: LocalizedText
    input_type: QuestionType
    required: bool = True
    priority: int = 10
    options: List[OptionChoice] = Field(default_factory=list)
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    section: str = "hpi"

class QuestionPrompt(BaseModel):
    field_name: str
    prompt_text: str
    input_type: QuestionType
    options: List[Dict[str, str]] = Field(default_factory=list)
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    progress_current: int = 1
    progress_total: int = 10
    section: str = "hpi"
