from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import crud, schemas, models, auth
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/patients", tags=["Patients"])

@router.post(
    "/register", 
    response_model=schemas.PatientRegisterResponse, 
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Patient and User account registered successfully"},
        400: {"description": "Validation error on registration fields"},
        409: {"description": "Username already exists"}
    }
)
def register_patient(
    reg_in: schemas.PatientRegisterRequest,
    db: Session = Depends(get_db)
):
    """Public self-registration endpoint for patients across all parts."""
    full_name = (reg_in.full_name or "").strip()
    username = (reg_in.username or "").strip()
    password = (reg_in.password or "").strip()

    if not full_name or not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name, username, and password are required."
        )

    try:
        patient, user = crud.register_patient_with_user(db, reg_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{str(e)}. Please choose another username or log in."
        )

    token = auth.create_access_token(data={"sub": user.username, "role": "PATIENT"})
    log_audit_event(db, user_id=user.username, action="PATIENT_SELF_REGISTERED", target_id=patient.patient_id)
    return {
        "patient_id": patient.patient_id,
        "username": user.username,
        "full_name": patient.name,
        "preferred_language": patient.preferred_language or "English",
        "access_token": token,
        "token_type": "bearer",
        "role": "PATIENT"
    }

@router.post("", response_model=schemas.PatientResponse)
def create_patient(
    patient_in: schemas.PatientCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    patient = crud.create_patient(db, patient_in)
    log_audit_event(db, user_id=current_user.username, action="PATIENT_CREATED", target_id=patient.patient_id)
    return patient

@router.get("", response_model=List[schemas.PatientResponse])
def list_patients(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Patient role can only view self
    if current_user.role == "PATIENT":
        if not current_user.patient_id:
            return []
        p = crud.get_patient(db, current_user.patient_id)
        return [p] if p else []
    return crud.list_patients(db)

@router.get("/{patient_id}", response_model=schemas.PatientResponse)
def get_patient(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Enforce patient data isolation
    if current_user.role == "PATIENT" and current_user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied to this patient record")

    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    log_audit_event(db, user_id=current_user.username, action="DOCTOR_VIEWED_RECORD" if current_user.role == "DOCTOR" else "PATIENT_VIEWED_RECORD", target_id=patient_id)
    return patient

@router.get("/{patient_id}/visits", response_model=List[schemas.VisitResponse])
def get_patient_visits(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role == "PATIENT" and current_user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied to this patient visit history")
    return crud.get_patient_visits(db, patient_id)

@router.get("/{patient_id}/documents", response_model=List[schemas.DocumentResponse])
def get_patient_documents(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role == "PATIENT" and current_user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied to patient documents")
    return crud.get_patient_documents(db, patient_id)

@router.get("/{patient_id}/prescriptions", response_model=List[schemas.PrescriptionResponse])
def get_patient_prescriptions(
    patient_id: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role == "PATIENT" and current_user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied to patient prescriptions")
    return crud.get_patient_prescriptions(db, patient_id)
