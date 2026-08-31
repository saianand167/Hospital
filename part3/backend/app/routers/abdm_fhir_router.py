from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, models, auth
from app.services.abdm_fhir import (
    mock_abdm_service, patient_to_fhir, clinical_history_to_fhir, 
    lab_report_to_fhir, prescription_to_fhir
)

router = APIRouter(prefix="/interop", tags=["ABDM & FHIR Interoperability"])

@router.post("/abdm/create-record/{patient_id}")
def create_abdm_record(
    patient_id: str,
    record_type: str = "OPD_CONSULTATION",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    visits = crud.get_patient_visits(db, patient_id)
    latest_visit = visits[0] if visits else None
    
    data_payload = {
        "name": patient.name,
        "visit_count": len(visits),
        "latest_visit_id": latest_visit.visit_id if latest_visit else None
    }

    record = mock_abdm_service.create_record(patient_id, record_type, data_payload)
    return record

@router.get("/fhir/patient/{patient_id}")
def export_patient_fhir(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    return patient_to_fhir({
        "patient_id": patient.patient_id,
        "name": patient.name,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "phone": patient.phone
    })

@router.get("/fhir/history/{visit_id}")
def export_history_fhir(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    ch = crud.get_clinical_history(db, visit_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Clinical history not found")

    payload = ch.history_json.copy()
    payload["patient_id"] = ch.patient_id
    payload["visit_id"] = ch.visit_id
    return clinical_history_to_fhir(payload)

@router.get("/fhir/prescription/{prescription_id}")
def export_prescription_fhir(
    prescription_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    rx = db.query(models.Prescription).filter(models.Prescription.prescription_id == prescription_id).first()
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")

    items = [{"medicine_name": i.medicine_name, "dose": i.dose, "route": i.route, "frequency": i.frequency, "duration": i.duration, "instructions": i.instructions} for i in rx.items]
    return prescription_to_fhir({
        "patient_id": rx.patient_id,
        "prescription_id": rx.prescription_id,
        "status": rx.status,
        "items": items
    })
