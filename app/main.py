import sys
from pathlib import Path

hospital_root = Path(__file__).resolve().parent.parent
if str(hospital_root) not in sys.path:
    sys.path.insert(0, str(hospital_root))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth_routes import router as auth_router
from app.api.session_routes import router as session_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.clinical.symptom_loader import SymptomLoader

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Part 1: Real-Time Multilingual Clinical History & Conversational AI Intake Engine (SIH26047)"
)

# CORS middleware for Streamlit & external Part 3 integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(auth_router)
app.include_router(session_router)

@app.on_event("startup")
def on_startup():
    init_db()
    SymptomLoader.load_all()
    from app.asr.indic_asr import IndicASR
    IndicASR.preload()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
