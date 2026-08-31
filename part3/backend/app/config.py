import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load environment: check root .env, then part3 .env ────────────────────────
_here = Path(__file__).resolve()
_root_env = _here.parents[3] / ".env"     # hospital/.env
_local_env = _here.parents[2] / ".env"    # hospital/part3/.env
_pwd_env = Path.cwd() / ".env"

for _p in [_root_env, _local_env, _pwd_env]:
    if _p.exists():
        load_dotenv(_p, override=True)


class Settings:
    PROJECT_NAME: str = "SIH26047 - MediKiosk"
    API_V1_STR: str = "/api/v1"

    # ── PostgreSQL ───────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://medikiosk_user:medikiosk_pass_2026@localhost:5433/medikiosk_db"
    )

    # ── Groq / Grok LLM ─────────────────────────────────────────────
    GROK_API_KEY: str = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY", "")
    GROK_API_BASE: str = (
        os.getenv("GROQ_API_BASE")
        or os.getenv("GROK_API_BASE", "https://api.groq.com/openai/v1")
    )
    GROK_MODEL: str = (
        os.getenv("GROQ_MODEL")
        or os.getenv("GROK_MODEL", "openai/gpt-oss-120b")
    )

    # ── JWT Auth ─────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "medikiosk_super_secret_jwt_key_2026_sih")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ── File Storage (Windows-safe relative path) ────────────────────
    # Default: ./uploads relative to the working directory
    STORAGE_DIR: str = os.getenv(
        "STORAGE_DIR",
        str(Path(__file__).resolve().parents[4] / "uploads")
    )

    # ── Embeddings ───────────────────────────────────────────────────
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5"
    )
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    USE_HF_EMBEDDINGS_API: bool = (
        os.getenv("USE_HF_EMBEDDINGS_API", "false").lower() == "true"
    )

    # ── OCR Configuration ────────────────────────────────────────────
    OCR_PROVIDER: str = os.getenv("OCR_PROVIDER", "tesseract")
    TESSERACT_CMD: str = os.getenv(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

    # ── Mock Mode ────────────────────────────────────────────────────
    MOCK_MODE: bool = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes")


settings = Settings()
