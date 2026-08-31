from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import uuid
import datetime
import asyncio
from functools import partial

from app.config import settings
from app.database import get_db
from app import crud, schemas, models, auth
from app.services.document_processing.pipeline import DocumentProcessingPipeline
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/documents", tags=["Medical Documents"])

@router.post("", response_model=schemas.DocumentResponse)
def create_document(
    doc_in: schemas.DocumentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    doc = crud.create_document(db, doc_in)
    log_audit_event(db, user_id=current_user.username, action="DOCUMENT_UPLOADED", target_id=doc.document_id)
    return doc

@router.post("/upload", response_model=schemas.DocumentResponse)
async def upload_document_file(
    patient_id: str = Form(...),
    document_type: str = Form(...),
    visit_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1]
    saved_filename = f"{patient_id}_{uuid.uuid4().hex[:8]}{file_ext}"
    saved_path = os.path.join(settings.STORAGE_DIR, saved_filename)

    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)

    # Run Real Document Processing Pipeline in thread pool
    # (EasyOCR is CPU-bound and would block the async event loop)
    v_id = visit_id  # Keep None if not provided — avoids FK violations
    loop = asyncio.get_event_loop()
    doc_result = await loop.run_in_executor(
        None,  # uses default ThreadPoolExecutor
        partial(
            DocumentProcessingPipeline.process_upload,
            file_bytes=content,
            filename=file.filename,
            patient_id=patient_id,
            visit_id=v_id,
            document_type=document_type
        )
    )

    doc_in = schemas.DocumentCreate(
        patient_id=patient_id,
        visit_id=v_id,
        document_type=doc_result["document_type"],
        document_date=datetime.datetime.utcnow(),
        raw_text=doc_result.get("raw_text", ""),
        structured_data=doc_result.get("structured_data", {}),
        ocr_confidence=doc_result.get("ocr_confidence", 0.0),
        extraction_confidence=doc_result.get("ocr_confidence", 0.0),
        verification_required=not doc_result.get("verified", False),
        verified=doc_result.get("verified", False),
        file_reference=saved_path
    )
    doc = crud.create_document(db, doc_in)
    log_audit_event(db, user_id=current_user.username, action="DOCUMENT_UPLOADED", target_id=doc.document_id)
    return doc

@router.post("/{document_id}/verify", response_model=schemas.DocumentResponse)
def verify_document(
    document_id: str,
    verify_in: schemas.DocumentVerifyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker(["PHARMACIST", "DOCTOR", "STAFF"]))
):
    doc = crud.verify_document(db, document_id, verify_in.verified, verify_in.structured_data)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    log_audit_event(db, user_id=current_user.username, action="DOCUMENT_VERIFIED", target_id=document_id)
    return doc

@router.get("/unverified", response_model=List[schemas.DocumentResponse])
def get_unverified_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker(["PHARMACIST", "DOCTOR", "STAFF"]))
):
    return db.query(models.Document).filter(
        models.Document.verification_required == True,
        models.Document.verified == False
    ).all()

@router.get("/{document_id}/download")
def download_document_file(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from fastapi.responses import FileResponse
    doc = db.query(models.Document).filter(models.Document.document_id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role == "PATIENT" and current_user.patient_id != doc.patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not doc.file_reference or not os.path.exists(doc.file_reference):
        raise HTTPException(status_code=404, detail="Original document file not found on disk")

    log_audit_event(db, user_id=current_user.username, action="DOCUMENT_DOWNLOADED", target_id=document_id)
    filename = os.path.basename(doc.file_reference)
    return FileResponse(path=doc.file_reference, filename=filename)

