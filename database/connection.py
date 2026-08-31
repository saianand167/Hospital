import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment from root .env
_root_env = Path(__file__).resolve().parent.parent / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=False)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://medikiosk_user:medikiosk_pass_2026@localhost:5433/medikiosk_db"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Yield database session and close safely upon completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_health() -> bool:
    """Check if PostgreSQL database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
