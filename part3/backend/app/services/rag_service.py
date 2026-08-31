from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
import json
import logging

from app import models
from app.services.embedding_service import embedding_provider
from app.services.llm_service import grok_service

logger = logging.getLogger(__name__)

def index_patient_data(db: Session, patient_id: str):
    """
    Build/update embedding index for a specific patient's clinical history, 
    documents, and prescriptions.
    """
    # Clear existing embeddings for this patient to re-index cleanly
    db.query(models.Embedding).filter(models.Embedding.patient_id == patient_id).delete()
    db.commit()

    embeddings_to_add = []

    # 1. Clinical Histories
    histories = db.query(models.ClinicalHistory).filter(models.ClinicalHistory.patient_id == patient_id).all()
    for hist in histories:
        content_text = f"Clinical History Visit {hist.visit_id}: " + json.dumps(hist.history_json)
        emb_vector = embedding_provider.embed(content_text)
        embeddings_to_add.append(models.Embedding(
            patient_id=patient_id,
            visit_id=hist.visit_id,
            source_type="CLINICAL_HISTORY",
            content=content_text,
            embedding=emb_vector
        ))

    # 2. Documents
    documents = db.query(models.Document).filter(models.Document.patient_id == patient_id).all()
    for doc in documents:
        content_text = f"Document {doc.document_id} ({doc.document_type}, Date: {doc.document_date}): Raw: {doc.raw_text or ''} Structured: {json.dumps(doc.structured_data or {})}"
        emb_vector = embedding_provider.embed(content_text)
        embeddings_to_add.append(models.Embedding(
            patient_id=patient_id,
            visit_id=doc.visit_id,
            document_id=doc.document_id,
            source_type=f"DOCUMENT_{doc.document_type}",
            content=content_text,
            embedding=emb_vector
        ))

    # 3. Prescriptions
    prescriptions = db.query(models.Prescription).filter(models.Prescription.patient_id == patient_id).all()
    for rx in prescriptions:
        items_str = ", ".join([f"{item.medicine_name} {item.dose} {item.frequency} ({item.duration})" for item in rx.items])
        content_text = f"Prescription {rx.prescription_id} Visit {rx.visit_id}: Status: {rx.status}. Items: {items_str}"
        emb_vector = embedding_provider.embed(content_text)
        embeddings_to_add.append(models.Embedding(
            patient_id=patient_id,
            visit_id=rx.visit_id,
            source_type="PRESCRIPTION",
            content=content_text,
            embedding=emb_vector
        ))

    if embeddings_to_add:
        db.bulk_save_objects(embeddings_to_add)
        db.commit()
        logger.info(f"Indexed {len(embeddings_to_add)} records for patient_id={patient_id}")

def search_patient_records(db: Session, patient_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Perform STRICT patient-isolated retrieval.
    WHERE patient_id = :patient_id is MANDATORY.
    """
    # Make sure latest records are indexed
    index_patient_data(db, patient_id)

    query_vector = embedding_provider.embed(query)
    
    # Check if pgvector vector operator <-> works or fetch filtered records for python distance
    records = db.query(models.Embedding).filter(models.Embedding.patient_id == patient_id).all()
    if not records:
        return []

    # Calculate cosine similarity or euclidean distance
    scored_records = []
    import numpy as np

    q_vec = np.array(query_vector, dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)

    for rec in records:
        if rec.embedding is not None:
            r_vec = np.array(rec.embedding, dtype=np.float32)
            r_norm = np.linalg.norm(r_vec)
            if q_norm > 0 and r_norm > 0:
                similarity = float(np.dot(q_vec, r_vec) / (q_norm * r_norm))
            else:
                similarity = 0.0
        else:
            # Full-text string match score fallback
            similarity = 1.0 if any(word in rec.content.lower() for word in query.lower().split()) else 0.0

        scored_records.append({
            "source_id": rec.document_id or rec.visit_id or f"EMB-{rec.id}",
            "source_type": rec.source_type,
            "document_date": str(rec.visit_id or rec.patient_id),
            "content": rec.content,
            "score": similarity
        })

    # Sort descending by similarity
    scored_records.sort(key=lambda x: x["score"], reverse=True)
    return scored_records[:top_k]

def query_patient_rag(db: Session, patient_id: str, query: str) -> Dict[str, Any]:
    """
    Full patient-isolated RAG pipeline:
    1. Authenticate / isolate by patient_id
    2. Retrieve top chunks for patient_id ONLY
    3. Generate grounded answer via Grok
    """
    retrieved_chunks = search_patient_records(db, patient_id, query, top_k=5)
    rag_result = grok_service.rag_answer_query(query, retrieved_chunks)
    rag_result["patient_id"] = patient_id
    rag_result["query"] = query
    return rag_result
