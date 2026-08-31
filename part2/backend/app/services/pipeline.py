import os
import traceback
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Document, DocumentPage, OCRResult, DocumentChunk
from app.services.preprocessing import ImagePreprocessor
from app.services.ocr import get_ocr_provider
from app.services.rag import RAGService
from app.agents.classifier_agent import ClassifierAgent
from app.agents.extraction_agent import ExtractionAgent
from app.agents.validation_agent import ValidationAgent
from app.utils.date_normalizer import normalize_date
from app.config import settings

def run_document_pipeline(document_id: str):
    """
    Executes the entire document digitization and intelligence pipeline.
    Invoked as an asynchronous background task.
    """
    db: Session = SessionLocal()
    try:
        # 1. Fetch document from database
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            print(f"Pipeline error: Document {document_id} not found.")
            return

        # 2. Update status: Preprocessing
        doc.ocr_status = "preprocessing"
        db.commit()

        # Generate preprocessed file path
        original_path = doc.storage_path
        preprocessed_filename = f"processed_{os.path.basename(original_path)}"
        preprocessed_relative = os.path.join("processed", preprocessed_filename)
        preprocessed_absolute = os.path.join(settings.storage_dir, preprocessed_relative)

        # Calculate quality score
        quality_info = ImagePreprocessor.calculate_quality_score(original_path)
        doc.quality_score = quality_info.get("quality_score", 1.0)
        
        if quality_info.get("status") == "needs_better_scan":
            doc.ocr_status = "failed"
            doc.extraction_status = "failed"
            doc.verification_status = "needs_review"
            doc.structured_data = {
                "error": "Document scan quality is too low.",
                "issues": quality_info.get("issues", [])
            }
            db.commit()
            return

        # Run preprocessing (denoise, deskew, enhanced contrast)
        preprocessing_success = ImagePreprocessor.preprocess(original_path, preprocessed_absolute)
        if not preprocessing_success:
            # Fallback to original image if preprocessing fails
            preprocessed_absolute = original_path
            preprocessed_relative = doc.storage_path.replace("originals/", "")

        # Save processed page relation
        page = DocumentPage(
            document_id=doc.id,
            page_number=1,
            image_path=preprocessed_relative
        )
        db.add(page)
        db.commit()

        # 3. Update status: OCR Processing
        doc.ocr_status = "ocr_processing"
        db.commit()

        ocr_provider = get_ocr_provider(settings.ocr_provider)
        ocr_words = ocr_provider.extract_text(preprocessed_absolute)

        if not ocr_words:
            doc.ocr_status = "failed"
            doc.extraction_status = "failed"
            db.commit()
            return

        # Save individual OCR results and compile raw text
        raw_text_parts = []
        for word in ocr_words:
            db_word = OCRResult(
                document_id=doc.id,
                page_number=word.page,
                text=word.text,
                confidence=word.confidence,
                bbox=word.bbox
            )
            db.add(db_word)
            raw_text_parts.append(word.text)

        raw_text = " ".join(raw_text_parts)
        doc.raw_text = raw_text
        doc.ocr_status = "completed"
        db.commit()

        # 4. Update status: Classified
        doc.extraction_status = "classifying"
        db.commit()

        doc_type, class_conf = ClassifierAgent.classify(raw_text)
        doc.document_type = doc_type
        db.commit()

        # 5. Update status: Extracting
        doc.extraction_status = "extracting"
        db.commit()

        raw_extracted_data = ExtractionAgent.extract(doc_type, raw_text)

        # 6. Update status: Validating
        doc.extraction_status = "validating"
        db.commit()

        validation_result = ValidationAgent.validate(doc_type, raw_extracted_data)
        
        # Normalize document dates if extracted
        doc_date = None
        date_conf = 0.0
        if doc_type == "prescription" and raw_extracted_data.get("date"):
            norm_val, _, conf = normalize_date(raw_extracted_data["date"])
            doc_date = norm_val
            date_conf = conf
        elif doc_type == "lab_report" and raw_extracted_data.get("report_date"):
            norm_val, _, conf = normalize_date(raw_extracted_data["report_date"])
            doc_date = norm_val
            date_conf = conf
        elif doc_type == "discharge_summary" and raw_extracted_data.get("discharge_date"):
            norm_val, _, conf = normalize_date(raw_extracted_data["discharge_date"])
            doc_date = norm_val
            date_conf = conf
        elif doc_type == "radiology_report" and raw_extracted_data.get("study_date"):
            norm_val, _, conf = normalize_date(raw_extracted_data["study_date"])
            doc_date = norm_val
            date_conf = conf

        doc.document_date = doc_date
        doc.overall_confidence = validation_result.get("overall_confidence", 0.0)
        doc.verification_status = validation_result.get("verification_status", "unverified")
        doc.structured_data = validation_result.get("structured_data", {})
        doc.extraction_status = "completed"
        db.commit()

        # 7. Index chunks for search/RAG
        chunks = RAGService.chunk_document(doc.id, doc.patient_id, raw_text, doc_type)
        for chunk in chunks:
            db_chunk = DocumentChunk(
                document_id=chunk["document_id"],
                patient_id=chunk["patient_id"],
                chunk_index=chunk["chunk_index"],
                text_content=chunk["text_content"],
                page_number=chunk["page_number"],
                section_name=chunk["section_name"]
            )
            db.add(db_chunk)
        db.commit()

    except Exception as e:
        print(f"Pipeline processing failed for document {document_id}:")
        traceback.print_exc()
        try:
            # Mark document as failed
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.ocr_status = "failed"
                doc.extraction_status = "failed"
                doc.structured_data = {"error": str(e)}
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
