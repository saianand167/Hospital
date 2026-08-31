from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel

from app.database import get_db
from app import crud, schemas, models, auth
from app.services.clinical_history.engine import RealHistoryEngine, RedFlagRuleEngine, ClinicalHistoryJSON
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/history", tags=["Clinical History"])

class SessionStartRequest(BaseModel):
    patient_id: str
    visit_id: str
    language: str = "en"
    initial_complaint: Optional[str] = None

class SessionMessageRequest(BaseModel):
    patient_message: str
    target_field: Optional[str] = None
    is_touch_input: bool = False
    touch_value: Optional[str] = None
    language: str = "en"

@router.post("", response_model=schemas.ClinicalHistoryResponse)
def store_clinical_history(
    history_in: schemas.ClinicalHistoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    ch = crud.create_or_update_clinical_history(db, history_in)
    log_audit_event(db, user_id=current_user.username, action="CLINICAL_HISTORY_STORED", target_id=history_in.visit_id)
    return ch

@router.get("/{visit_id}", response_model=schemas.ClinicalHistoryResponse)
def get_clinical_history(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    ch = crud.get_clinical_history(db, visit_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Clinical history not found for this visit")

    if current_user.role == "PATIENT" and current_user.patient_id != ch.patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ch

@router.post("/session/start")
def start_history_session(
    req: SessionStartRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    history, next_prompt = RealHistoryEngine.start_session(
        patient_id=req.patient_id,
        visit_id=req.visit_id,
        language=req.language,
        initial_complaint=req.initial_complaint
    )
    return {
        "status": "session_started",
        "history": history.model_dump(),
        "next_question": next_prompt.model_dump() if next_prompt else None,
        "is_completed": history.metadata.completed
    }

@router.post("/session/{visit_id}/message")
def send_history_message(
    visit_id: str,
    req: SessionMessageRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    history, next_prompt, is_completed = RealHistoryEngine.process_message(
        visit_id=visit_id,
        patient_message=req.patient_message,
        target_field=req.target_field,
        is_touch_input=req.is_touch_input,
        touch_value=req.touch_value,
        language=req.language
    )

    # Persist in DB if red flag triggered or session completed
    if is_completed or history.triage.flag == "RED":
        history_in = schemas.ClinicalHistoryCreate(
            visit_id=visit_id,
            patient_id=history.patient_id,
            history_json=history.model_dump(),
            source="Part1_Real_Clinical_Engine"
        )
        crud.create_or_update_clinical_history(db, history_in)
        log_audit_event(db, user_id=current_user.username, action="CLINICAL_INTAKE_COMPLETED", target_id=visit_id)

    return {
        "history": history.model_dump(),
        "next_question": next_prompt.model_dump() if next_prompt else None,
        "is_completed": is_completed,
        "triage": history.triage.model_dump()
    }

@router.get("/session/{visit_id}/next-question")
def get_next_question(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    history = RealHistoryEngine.get_session(visit_id)
    if not history:
        raise HTTPException(status_code=404, detail="Active history session not found")

    from app.services.clinical_history.engine import ClinicalQuestionEngine
    prompt, is_completed = ClinicalQuestionEngine.get_next_question(history)
    return {
        "next_question": prompt.model_dump() if prompt else None,
        "is_completed": is_completed,
        "triage": history.triage.model_dump()
    }

@router.post("/mock-generate/{visit_id}", response_model=schemas.ClinicalHistoryResponse)
def generate_mock_part1_history(
    visit_id: str,
    chief_complaint: str = "Chest pain",
    is_red_flag: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    visit = crud.get_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    history, _, _ = RealHistoryEngine.process_message(
        visit_id=visit_id,
        patient_message=chief_complaint,
        target_field="chief_complaint"
    )
    if is_red_flag:
        history.triage.flag = "RED"
        history.triage.priority = True
        history.triage.reason_codes = ["SEVERE_CHEST_PAIN_RED_FLAG"]

    history_in = schemas.ClinicalHistoryCreate(
        visit_id=visit_id,
        patient_id=visit.patient_id,
        history_json=history.model_dump(),
        source="Part1_Real_Clinical_Engine"
    )
    ch = crud.create_or_update_clinical_history(db, history_in)
    log_audit_event(db, user_id=current_user.username, action="MOCK_HISTORY_GENERATED", target_id=visit_id)
    return ch
