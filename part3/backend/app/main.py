from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sqlalchemy
import threading

from app.config import settings
from app.database import engine, Base, SessionLocal
from app import crud, models
from app.routers import (
    auth, patients, visits, history, documents,
    prescriptions, doctor, rag, health, abdm_fhir_router, voice
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medikiosk")

# Database initialization on startup
try:
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    logger.info("pgvector extension ensured.")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        crud.seed_default_users(db)
    logger.info("MediKiosk PostgreSQL startup complete: tables created and seeded.")
except Exception as e:
    logger.error(
        "\n========================================================================\n"
        "[DATABASE ERROR] PostgreSQL database is not reachable!\n"
        "Please start the PostgreSQL + pgvector database using Docker Compose:\n"
        "    docker compose up -d\n"
        f"Underlying error: {e}\n"
        "========================================================================"
    )

# Pre-warm EasyOCR model in background thread to eliminate cold-start on first upload
def _warm_up_easyocr():
    try:
        from app.services.document_processing.pipeline import get_easyocr_reader
        reader = get_easyocr_reader()
        if reader:
            logger.info("✅ EasyOCR model preloaded and ready.")
        else:
            logger.info("EasyOCR not available — Tesseract will be used if installed.")
    except Exception as e:
        logger.warning(f"EasyOCR warm-up failed (non-critical): {e}")

threading.Thread(target=_warm_up_easyocr, daemon=True).start()
logger.info("EasyOCR warm-up started in background thread...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MediKiosk SIH26047 — Integrated Patient Records, Doctor Panel, RAG & Multi-Part Integration Layer",
    version="1.0.0"
)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handler — suppress stack traces from reaching the user
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please contact the system administrator."}
    )

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "SIH26047 - MediKiosk Backend API",
        "version": "1.0.0",
        "database": "Connected (Neon PostgreSQL + pgvector)",
        "api_documentation": "/docs",
        "health_check": "/health",
        "api_v1_base": "/api/v1"
    }

# Include Routers
app.include_router(health.router)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(patients.router, prefix=settings.API_V1_STR)
app.include_router(visits.router, prefix=settings.API_V1_STR)
app.include_router(history.router, prefix=settings.API_V1_STR)
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(prescriptions.router, prefix=settings.API_V1_STR)
app.include_router(doctor.router, prefix=settings.API_V1_STR)
app.include_router(rag.router, prefix=settings.API_V1_STR)
app.include_router(abdm_fhir_router.router, prefix=settings.API_V1_STR)
app.include_router(voice.router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
