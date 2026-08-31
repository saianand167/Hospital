"""
MediKiosk Part 2 — Medical Document Intelligence API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.documents import router as doc_router

app = FastAPI(
    title="MediKiosk — Document Intelligence",
    description="Part 2: Medical Document Digitization, Classification, Extraction & Storage",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(doc_router)

@app.get("/health")
def health():
    from app.config import settings
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "ocr_provider": settings.ocr_provider,
        "mock_mode": settings.mock_mode,
    }
