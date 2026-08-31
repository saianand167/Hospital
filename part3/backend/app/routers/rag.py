from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas, models, auth
from app.services.rag_service import query_patient_rag
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/patients", tags=["RAG Retrieval"])

@router.post("/{patient_id}/query", response_model=schemas.RAGQueryResponse)
def query_patient_records(
    patient_id: str,
    query_req: schemas.RAGQueryRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Enforce patient data isolation rule
    if current_user.role == "PATIENT" and current_user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied to query patient records")

    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Perform patient-isolated RAG search
    result = query_patient_rag(db, patient_id=patient_id, query=query_req.query)
    
    log_audit_event(
        db, 
        user_id=current_user.username, 
        action="RAG_QUERY_EXECUTED", 
        target_id=patient_id,
        details={"query": query_req.query, "sources_count": len(result.get("sources", []))}
    )
    
    return result
