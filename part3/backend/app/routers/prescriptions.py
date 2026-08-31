from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os

from app.config import settings
from app.database import get_db
from app import crud, schemas, models, auth
from app.services.prescription_service import parse_voice_dictation, generate_prescription_pdf
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])

@router.post("/voice-dictate", response_model=List[schemas.PrescriptionItemCreate])
def process_voice_dictation(
    dictation_req: schemas.VoicePrescriptionRequest,
    current_user: models.User = Depends(auth.RoleChecker(["DOCTOR"]))
):
    """
    Doctor records prescription speech -> STT -> Returns structured draft items for doctor review.
    AI NEVER autonomosly finalizes prescription.
    """
    items = parse_voice_dictation(dictation_req.transcript)
    return items

@router.post("", response_model=schemas.PrescriptionResponse)
def create_draft_prescription(
    rx_in: schemas.PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker(["DOCTOR"]))
):
    rx = crud.create_prescription(db, rx_in)
    log_audit_event(db, user_id=current_user.username, action="PRESCRIPTION_CREATED", target_id=rx.prescription_id)
    return rx

@router.post("/{prescription_id}/confirm", response_model=schemas.PrescriptionResponse)
def confirm_prescription(
    prescription_id: str,
    confirm_in: schemas.PrescriptionConfirmRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker(["DOCTOR"]))
):
    rx = crud.confirm_prescription(db, prescription_id, confirm_in.items)
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")

    patient = crud.get_patient(db, rx.patient_id)
    patient_name = patient.name if patient else "Patient"

    doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == rx.doctor_id).first()
    doctor_name = doctor.name if doctor else f"Dr. {current_user.username}"

    # Prepare item dicts
    item_dicts = [
        {
            "medicine_name": item.medicine_name,
            "dose": item.dose,
            "route": item.route,
            "frequency": item.frequency,
            "duration": item.duration,
            "instructions": item.instructions
        }
        for item in rx.items
    ]

    # Generate PDF
    generate_prescription_pdf(
        prescription_id=rx.prescription_id,
        patient_name=patient_name,
        patient_id=rx.patient_id,
        doctor_name=doctor_name,
        visit_id=rx.visit_id,
        date_str=rx.created_at.strftime("%Y-%m-%d"),
        items=item_dicts
    )

    log_audit_event(db, user_id=current_user.username, action="PRESCRIPTION_CONFIRMED", target_id=prescription_id)
    return rx

@router.get("/{prescription_id}/pdf")
def get_prescription_pdf(
    prescription_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    rx = db.query(models.Prescription).filter(models.Prescription.prescription_id == prescription_id).first()
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")

    if current_user.role == "PATIENT" and current_user.patient_id != rx.patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    pdf_path = os.path.join(settings.STORAGE_DIR, "prescriptions", f"{prescription_id}.pdf")
    if not os.path.exists(pdf_path):
        # Generate if missing
        patient = crud.get_patient(db, rx.patient_id)
        doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == rx.doctor_id).first()
        item_dicts = [{"medicine_name": i.medicine_name, "dose": i.dose, "route": i.route, "frequency": i.frequency, "duration": i.duration, "instructions": i.instructions} for i in rx.items]
        generate_prescription_pdf(
            prescription_id=rx.prescription_id,
            patient_name=patient.name if patient else "Patient",
            patient_id=rx.patient_id,
            doctor_name=doctor.name if doctor else "Doctor",
            visit_id=rx.visit_id,
            date_str=rx.created_at.strftime("%Y-%m-%d"),
            items=item_dicts
        )

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{prescription_id}.pdf")
