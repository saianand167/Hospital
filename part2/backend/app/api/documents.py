"""
Documents API — Part 2 MediKiosk.

Endpoints:
  POST   /documents/upload
  GET    /documents/{doc_id}
  GET    /documents/{doc_id}/extraction
  GET    /documents/{doc_id}/original
  POST   /documents/{doc_id}/verify
  POST   /documents/{doc_id}/reprocess
  GET    /patients/{patient_id}/documents
  GET    /patients/{patient_id}/timeline
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
import os
import shutil

from app.config import settings
from app.utils.security import validate_uploaded_file, sanitize_filename
from app.schemas.documents import (
    StructuredDocument, DocumentType, DocumentMetadata,
    OCRResult, OCRPage, ClassificationResult, ExtractionResult,
    VerificationInfo, ConfidenceModel, VerifyRequest
)
from app.services.preprocessing import pil_from_bytes, preprocess_for_ocr, assess_image_quality
from app.services.pdf_processor import is_text_pdf, extract_text_from_pdf, render_pdf_pages
from app.services.ocr import get_ocr_provider
from app.agents.classifier_agent import DocumentClassifier
from app.agents.extraction_agent import ExtractionAgent
from app.agents.validation_agent import ValidationAgent

router = APIRouter(tags=["Documents"])

# In-memory store — keyed by document_id
DOCUMENT_STORE: Dict[str, StructuredDocument] = {}


# ─── Core pipeline ────────────────────────────────────────────────────────────

def process_file_pipeline(
    file_bytes: bytes,
    filename: str,
    ext: str,
    language: str = "eng",
    patient_id: Optional[str] = None,
    visit_id: Optional[str] = None,
) -> StructuredDocument:
    """Full document intelligence pipeline."""
    document_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    upload_timestamp = datetime.utcnow().isoformat()

    # ── 1. Save original file permanently ────────────────────────────────────
    safe_name = sanitize_filename(filename)
    original_path = os.path.join(
        settings.original_docs_dir,
        f"{document_id}_{safe_name}"
    )
    with open(original_path, "wb") as f:
        f.write(file_bytes)

    # ── 2. OCR ────────────────────────────────────────────────────────────────
    ocr_pages: List[OCRPage] = []
    ocr_confidence_scores: List[float] = []
    ocr_provider = get_ocr_provider(settings.ocr_provider)

    if ext == ".pdf":
        try:
            if is_text_pdf(file_bytes):
                # Text-based PDF: extract selectable text directly (100% confidence)
                text_pages = extract_text_from_pdf(file_bytes)
                for page_num, text in text_pages:
                    if text.strip():   # skip blank pages
                        ocr_pages.append(OCRPage(page=page_num, text=text, confidence=1.0))
                        ocr_confidence_scores.append(1.0)
            else:
                # Scanned PDF: render each page as PIL Image then OCR
                # render_pdf_pages() returns List[Tuple[int, PIL.Image]] — NOT bytes
                rendered_pages = render_pdf_pages(file_bytes)
                for page_num, pil_img in rendered_pages:
                    # pil_img is already a PIL Image — do NOT call pil_from_bytes() on it
                    preprocessed = preprocess_for_ocr(pil_img)
                    result = ocr_provider.extract(preprocessed, language=language)
                    if result.text.strip():
                        ocr_pages.append(OCRPage(page=page_num, text=result.text, confidence=result.confidence))
                        ocr_confidence_scores.append(result.confidence)
        except Exception as e:
            print(f"PDF processing error: {e}")
            return _failed_doc(document_id, filename, original_path, patient_id, visit_id, upload_timestamp, f"PDF processing failed: {e}")
    else:
        # Image file: convert bytes -> PIL Image -> assess quality -> preprocess -> OCR
        try:
            img = pil_from_bytes(file_bytes)
            quality_info = assess_image_quality(img)
            preprocessed = preprocess_for_ocr(img)
            result = ocr_provider.extract(preprocessed, language=language)
            ocr_pages.append(OCRPage(page=1, text=result.text, confidence=result.confidence))
            ocr_confidence_scores.append(result.confidence)
        except Exception as e:
            return _failed_doc(document_id, filename, original_path, patient_id, visit_id, upload_timestamp, f"OCR failed: {e}")

    if not ocr_pages:
        return _failed_doc(document_id, filename, original_path, patient_id, visit_id, upload_timestamp, "No text extracted from document")

    full_text = "\n\n".join(p.text for p in ocr_pages)
    avg_ocr_confidence = sum(ocr_confidence_scores) / len(ocr_confidence_scores)

    # ── 3. Classification ─────────────────────────────────────────────────────
    doc_type, class_confidence = DocumentClassifier.classify(full_text, filename_hint=filename)

    # ── 4. Type-specific extraction ───────────────────────────────────────────
    try:
        extracted_data = ExtractionAgent.extract(doc_type, full_text)
        extraction_ok = True
    except Exception as e:
        print(f"Extraction error: {e}")
        extracted_data = {}
        extraction_ok = False

    # ── 5. Validation ─────────────────────────────────────────────────────────
    ext_confidence, requires_verify, status = ValidationAgent.validate(
        doc_type, extracted_data, avg_ocr_confidence, class_confidence
    )

    if not extraction_ok:
        status = "failed"
        ext_confidence = 0.0
        requires_verify = True

    # ── Update Quality Block and document_type in extracted_data ──────────────
    if doc_type == DocumentType.LAB_REPORT:
        if not isinstance(extracted_data, dict):
            extracted_data = {}
        extracted_data["document_type"] = "laboratory_report"
        if "quality" not in extracted_data or not isinstance(extracted_data["quality"], dict):
            extracted_data["quality"] = {}
        extracted_data["quality"]["ocr_quality"] = (
            "high" if avg_ocr_confidence > 0.85 
            else ("medium" if avg_ocr_confidence > 0.70 else "low")
        )
        extracted_data["quality"]["extraction_complete"] = (status == "success")
        extracted_data["quality"]["requires_verification"] = requires_verify

    # ── 6. Metadata from extraction (handle flat or nested structures) ────────
    ext_meta = extracted_data.get("metadata", {}) if isinstance(extracted_data.get("metadata"), dict) else {}
    doc_date = ext_meta.get("document_date") or extracted_data.get("document_date")
    hosp_name = ext_meta.get("hospital_name") or extracted_data.get("hospital_name")
    lab_name = ext_meta.get("laboratory_name") or extracted_data.get("laboratory_name")
    doc_name = ext_meta.get("doctor_name") or extracted_data.get("doctor_name")

    metadata = DocumentMetadata(
        document_date=doc_date,
        hospital_name=hosp_name,
        laboratory_name=lab_name,
        doctor_name=doc_name,
        language=language,
    )

    doc = StructuredDocument(
        document_id=document_id,
        patient_id=patient_id,
        visit_id=visit_id,
        document_type=doc_type,
        metadata=metadata,
        ocr=OCRResult(
            raw_text=full_text,
            pages=ocr_pages,
            language=language,
        ),
        classification=ClassificationResult(
            document_type=doc_type,
            confidence=round(class_confidence, 3),
            requires_verification=(class_confidence < settings.low_confidence_threshold),
        ),
        extraction=ExtractionResult(
            status=status,
            confidence=ext_confidence,
            message=extracted_data.get("_extraction_note"),
        ),
        confidence=ConfidenceModel(
            ocr=round(avg_ocr_confidence, 3),
            classification=round(class_confidence, 3),
            extraction=ext_confidence,
        ),
        data=extracted_data,
        verification=VerificationInfo(
            required=requires_verify,
            verified=False,
        ),
        upload_timestamp=upload_timestamp,
        file_name=filename,
        file_path=original_path,
    )

    DOCUMENT_STORE[document_id] = doc
    return doc


def _failed_doc(doc_id, filename, file_path, patient_id, visit_id, ts, reason) -> StructuredDocument:
    """Return a failed-status document record instead of raising an exception."""
    doc = StructuredDocument(
        document_id=doc_id,
        patient_id=patient_id,
        visit_id=visit_id,
        document_type=DocumentType.UNKNOWN,
        metadata=DocumentMetadata(),
        ocr=OCRResult(),
        classification=ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            requires_verification=True,
        ),
        extraction=ExtractionResult(status="failed", confidence=0.0, message=reason),
        confidence=ConfidenceModel(),
        data={},
        verification=VerificationInfo(required=True),
        upload_timestamp=ts,
        file_name=filename,
        file_path=file_path,
    )
    DOCUMENT_STORE[doc_id] = doc
    return doc


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    language: str = Query(default="eng", description="OCR language: eng, hin, tel"),
    patient_id: Optional[str] = Query(default=None),
    visit_id: Optional[str] = Query(default=None),
):
    """Upload and process a medical document."""
    validate_uploaded_file(file)
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File exceeds maximum allowed size of 10MB."
        )
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[-1].lower()
    doc = process_file_pipeline(file_bytes, filename, ext, language, patient_id, visit_id)
    return doc


@router.get("/documents/{document_id}")
def get_document(document_id: str):
    """Get full structured document by ID."""
    doc = DOCUMENT_STORE.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/documents/{document_id}/extraction")
def get_extraction(document_id: str):
    """Get only the extracted data for a document."""
    doc = DOCUMENT_STORE.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "document_id": document_id,
        "document_type": doc.document_type,
        "extraction_status": doc.extraction.status,
        "extraction_confidence": doc.extraction.confidence,
        "requires_verification": doc.verification.required,
        "data": doc.data,
    }


@router.get("/documents/{document_id}/original")
def get_original_document(document_id: str):
    """Serve the original uploaded document file."""
    doc = DOCUMENT_STORE.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Original file not found on disk")
    return FileResponse(
        path=doc.file_path,
        filename=doc.file_name,
        media_type="application/octet-stream"
    )


@router.post("/documents/{document_id}/verify")
def verify_document(document_id: str, body: VerifyRequest):
    """Staff/pharmacist verifies and corrects extracted data with full audit trail."""
    doc = DOCUMENT_STORE.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Audit trail: preserve original AI extraction before updating working data
    ai_extracted_snapshot = dict(doc.data)
    
    doc.verification.verified = True
    doc.verification.verified_by = body.verified_by
    doc.verification.corrected_data = {
        "ai_extracted_data": ai_extracted_snapshot,
        "corrected_data": body.corrected_data,
        "verified_by": body.verified_by,
        "verified_at": datetime.utcnow().isoformat(),
    }
    doc.data = body.corrected_data  # update working data with corrections
    doc.extraction.status = "verified"
    doc.verification.required = False
    DOCUMENT_STORE[document_id] = doc
    return {
        "status": "verified",
        "document_id": document_id,
        "verified_by": body.verified_by,
        "verified_at": doc.verification.corrected_data["verified_at"],
    }


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(document_id: str):
    """Re-run the full pipeline on the original file."""
    doc = DOCUMENT_STORE.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Original file not available for reprocessing")
    with open(doc.file_path, "rb") as f:
        file_bytes = f.read()
    ext = os.path.splitext(doc.file_name)[-1].lower()
    new_doc = process_file_pipeline(
        file_bytes, doc.file_name, ext,
        language=doc.ocr.language,
        patient_id=doc.patient_id,
        visit_id=doc.visit_id,
    )
    # Preserve original document_id
    DOCUMENT_STORE[document_id] = new_doc
    new_doc.document_id = document_id
    return new_doc


@router.get("/patients/{patient_id}/documents")
def get_patient_documents(patient_id: str):
    """Get all documents for a patient."""
    docs = [
        {
            "document_id": d.document_id,
            "document_type": d.document_type,
            "file_name": d.file_name,
            "upload_timestamp": d.upload_timestamp,
            "document_date": d.metadata.document_date,
            "extraction_status": d.extraction.status,
            "requires_verification": d.verification.required,
        }
        for d in DOCUMENT_STORE.values()
        if d.patient_id == patient_id
    ]
    docs.sort(key=lambda x: x["upload_timestamp"], reverse=True)
    return {"patient_id": patient_id, "total": len(docs), "documents": docs}


@router.get("/patients/{patient_id}/timeline")
def get_patient_timeline(patient_id: str):
    """Medical timeline for a patient — ordered by document date."""
    docs = [
        d for d in DOCUMENT_STORE.values() if d.patient_id == patient_id
    ]
    timeline = []
    for d in docs:
        date = d.metadata.document_date or d.upload_timestamp[:10]
        summary = _build_summary(d)
        timeline.append({
            "date": date,
            "document_id": d.document_id,
            "document_type": d.document_type,
            "file_name": d.file_name,
            "summary": summary,
            "has_abnormal": _has_abnormal(d),
            "extraction_status": d.extraction.status,
        })
    timeline.sort(key=lambda x: x["date"])
    return {"patient_id": patient_id, "timeline": timeline}


def _build_summary(doc: StructuredDocument) -> str:
    if doc.document_type == DocumentType.LAB_REPORT:
        sections = doc.data.get("sections", [])
        names = [s.get("section_name", "") for s in sections]
        return f"Lab Report: {', '.join(names)}" if names else "Lab Report"
    elif doc.document_type == DocumentType.PRESCRIPTION:
        meds = doc.data.get("medications", [])
        names = [m.get("name", "") for m in meds[:3]]
        return f"Prescription: {', '.join(names)}" if names else "Prescription"
    elif doc.document_type == DocumentType.DISCHARGE_SUMMARY:
        diags = doc.data.get("diagnoses", [])
        return f"Discharge: {', '.join(diags[:2])}" if diags else "Discharge Summary"
    elif doc.document_type == DocumentType.IMAGING_REPORT:
        modality = doc.data.get("modality", "")
        body = doc.data.get("body_part", "")
        return f"Imaging: {modality} {body}".strip()
    return doc.document_type.value


def _has_abnormal(doc: StructuredDocument) -> bool:
    if doc.document_type == DocumentType.LAB_REPORT:
        for section in doc.data.get("sections", []):
            for test in section.get("tests", []):
                if test.get("abnormal") is True:
                    return True
    return False
