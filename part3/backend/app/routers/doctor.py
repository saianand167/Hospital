from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.database import get_db
from app import crud, schemas, models, auth
from app.services.llm_service import grok_service
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/doctor", tags=["Doctor Panel"])

@router.get("/queue", response_model=List[schemas.VisitResponse])
def get_doctor_queue(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker(["DOCTOR", "STAFF"]))
):
    return crud.get_doctor_queue(db)

@router.get("/patients/{patient_id}/summary", response_model=schemas.DoctorSummaryResponse)
def get_patient_summary(
    patient_id: str,
    visit_id: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker(["DOCTOR", "STAFF"]))
):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Fetch current visit and history
    if visit_id:
        current_visit = crud.get_visit(db, visit_id)
    else:
        visits = crud.get_patient_visits(db, patient_id)
        current_visit = visits[0] if visits else None

    current_history_dict = {}
    triage_flag = "NORMAL"
    if current_visit:
        ch = crud.get_clinical_history(db, current_visit.visit_id)
        if ch:
            current_history_dict = ch.history_json
        triage_flag = current_visit.priority

    # Previous visits
    all_visits = crud.get_patient_visits(db, patient_id)
    prev_visits_data = []
    for v in all_visits:
        if current_visit and v.visit_id == current_visit.visit_id:
            continue
        v_ch = crud.get_clinical_history(db, v.visit_id)
        v_rx = db.query(models.Prescription).filter(models.Prescription.visit_id == v.visit_id).first()
        rx_items = [{"medicine_name": i.medicine_name, "dose": i.dose, "frequency": i.frequency} for i in v_rx.items] if v_rx else []
        prev_visits_data.append({
            "visit_id": v.visit_id,
            "visit_date": str(v.visit_date),
            "department": v.department,
            "chief_complaint": v_ch.history_json.get("chief_complaint") if v_ch else "Routine",
            "prescription": {"items": rx_items}
        })

    # Documents
    documents = crud.get_patient_documents(db, patient_id)
    docs_data = [
        {
            "document_id": d.document_id,
            "document_type": d.document_type,
            "document_date": str(d.document_date),
            "raw_text": d.raw_text,
            "structured_data": d.structured_data
        }
        for d in documents
    ]

    # Generate Doctor Summary via Grok (with fallback)
    summary_dict = grok_service.generate_doctor_summary(
        current_history=current_history_dict,
        previous_visits=prev_visits_data,
        documents=docs_data,
        triage_flag=triage_flag
    )

    sources = [
        {"source_id": f"VISIT-{current_visit.visit_id if current_visit else 'CUR'}", "type": "Current History"}
    ]
    for d in documents:
        sources.append({"source_id": d.document_id, "type": f"Document ({d.document_type})"})

    log_audit_event(db, user_id=current_user.username, action="SUMMARY_GENERATED", target_id=patient_id)

    return {
        "patient_id": patient_id,
        "visit_id": current_visit.visit_id if current_visit else None,
        "chief_complaint": summary_dict.get("chief_complaint", "Reported symptoms"),
        "hpi": summary_dict.get("hpi", ""),
        "relevant_past_history": summary_dict.get("relevant_past_history", ""),
        "medications": summary_dict.get("medications", []),
        "allergies": summary_dict.get("allergies", []),
        "family_personal_history": summary_dict.get("family_personal_history", ""),
        "relevant_previous_investigations": summary_dict.get("relevant_previous_investigations", ""),
        "previous_treatments": summary_dict.get("previous_treatments", ""),
        "current_triage_flag": summary_dict.get("current_triage_flag", triage_flag),
        "sources": sources
    }
