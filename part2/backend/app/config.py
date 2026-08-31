"""
Application Configuration.
Resolves .env from the project root (part2-document-intelligence/)
regardless of the CWD uvicorn is launched from.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Walk up: backend/app/config.py -> backend/ -> part2-document-intelligence/
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    llm_provider: str = Field(default="mock", validation_alias="LLM_PROVIDER")
    ocr_provider: str = Field(default="mock", validation_alias="OCR_PROVIDER")

    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    mock_mode: bool = Field(default=True, validation_alias="MOCK_MODE")

    storage_dir: str = Field(default="./temp_uploads", validation_alias="STORAGE_DIR")
    original_docs_dir: str = Field(default="./original_docs", validation_alias="ORIGINAL_DOCS_DIR")
    ocr_confidence_threshold: float = Field(default=0.75, validation_alias="OCR_CONFIDENCE_THRESHOLD")
    port: int = Field(default=8000, validation_alias="PORT")

    # Database
    database_url: str = Field(
        default="sqlite:///./medikiosk.db",
        validation_alias="DATABASE_URL"
    )

    # Confidence thresholds
    high_confidence_threshold: float = Field(default=0.80, validation_alias="HIGH_CONFIDENCE_THRESHOLD")
    low_confidence_threshold: float  = Field(default=0.55, validation_alias="LOW_CONFIDENCE_THRESHOLD")

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

os.makedirs(settings.storage_dir, exist_ok=True)
os.makedirs(settings.original_docs_dir, exist_ok=True)
