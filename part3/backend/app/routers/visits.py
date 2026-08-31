from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas, models, auth
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/visits", tags=["Visits"])

@router.post("", response_model=schemas.VisitResponse)
def create_visit(
    visit_in: schemas.VisitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    patient = crud.get_patient(db, visit_in.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    visit = crud.create_visit(db, visit_in)
    log_audit_event(db, user_id=current_user.username, action="VISIT_CREATED", target_id=visit.visit_id)
    return visit

@router.get("/{visit_id}", response_model=schemas.VisitResponse)
def get_visit(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    visit = crud.get_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    if current_user.role == "PATIENT" and current_user.patient_id != visit.patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return visit

@router.post("/{visit_id}/complete", response_model=schemas.VisitResponse)
def complete_visit(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    visit = crud.update_visit_status(db, visit_id, status="COMPLETED")
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    log_audit_event(db, user_id=current_user.username, action="VISIT_COMPLETED", target_id=visit_id)
    return visit
