import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Try loading .env or parent sai.env
env_paths = [
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent.parent / "sai.env"
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)

class Settings(BaseModel):
    PROJECT_NAME: str = "MediKiosk Part 1 - Clinical History Engine"
    VERSION: str = "1.0.0"
    API_PREFIX: str = ""
    
    # LLM API Keys
    GROK_API_KEY: str = os.getenv("GROK_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", os.getenv("groq_api_key", ""))
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", os.getenv("open_ai", ""))
    
    # Mock / Dev mode
    MOCK_MODE: bool = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes")
    
    # Default language
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: list[str] = ["en", "te", "hi"]
    
    # ASR Voice Model Settings (Local faster-whisper Medium + Swecha Gonthuka ASR)
    ASR_MODEL_SIZE: str = os.getenv("ASR_MODEL_SIZE", "medium")
    ASR_DEVICE: str = os.getenv("ASR_DEVICE", "auto")
    ASR_COMPUTE_TYPE: str = os.getenv("ASR_COMPUTE_TYPE", "int8")

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    CONFIG_DIR: Path = Path(__file__).resolve().parent.parent.parent / "config"
    SYMPTOMS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "config" / "symptoms"

settings = Settings()
