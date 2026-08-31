from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict, Any
import datetime
import uuid

from app import models, schemas
from app.auth import get_password_hash

# --- User & Seed Operations ---

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, username: str, password_raw: str, role: str, patient_id: str = None, doctor_id: str = None, pharmacist_id: str = None) -> models.User:
    hashed_pwd = get_password_hash(password_raw)
    user = models.User(
        username=username,
        password_hash=hashed_pwd,
        role=role,
        patient_id=patient_id,
        doctor_id=doctor_id,
        pharmacist_id=pharmacist_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def seed_default_users(db: Session):
    """Seed initial demo accounts if database is empty or missing them."""
    # Seed Doctor
    if not db.query(models.Doctor).filter(models.Doctor.doctor_id == "DOC-101").first():
        doc = models.Doctor(doctor_id="DOC-101", name="Dr. A. Sharma", department="Cardiology")
        db.add(doc)
        db.commit()
    if not db.query(models.User).filter(models.User.username == "doctor1").first():
        create_user(db, "doctor1", "doctor123", "DOCTOR", doctor_id="DOC-101")

    # Seed Pharmacist
    if not db.query(models.Pharmacist).filter(models.Pharmacist.pharmacist_id == "PHARM-101").first():
        pharm = models.Pharmacist(pharmacist_id="PHARM-101", name="Pharmacy Specialist")
        db.add(pharm)
        db.commit()
    if not db.query(models.User).filter(models.User.username == "pharm1").first():
        create_user(db, "pharm1", "pharm123", "PHARMACIST", pharmacist_id="PHARM-101")

    # Seed Staff
    if not db.query(models.User).filter(models.User.username == "staff1").first():
        create_user(db, "staff1", "staff123", "STAFF")

    # Seed Patient
    if not db.query(models.Patient).filter(models.Patient.patient_id == "PAT-000001").first():
        pat = models.Patient(
            patient_id="PAT-000001",
            name="Rajesh Kumar",
            date_of_birth="1984-05-12",
            gender="Male",
            phone="9876543210",
            preferred_language="Telugu / English"
        )
        db.add(pat)
        db.commit()
    if not db.query(models.User).filter(models.User.username == "patient1").first():
        create_user(db, "patient1", "patient123", "PATIENT", patient_id="PAT-000001")

# --- Patient Operations ---

def generate_patient_id(db: Session) -> str:
    count = db.query(models.Patient).count() + 1
    return f"PAT-{count:06d}"

def create_patient(db: Session, patient_in: schemas.PatientCreate) -> models.Patient:
    pid = generate_patient_id(db)
    patient = models.Patient(
        patient_id=pid,
        name=patient_in.name,
        date_of_birth=patient_in.date_of_birth,
        gender=patient_in.gender,
        phone=patient_in.phone,
        preferred_language=patient_in.preferred_language or "English"
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient

def register_patient_with_user(db: Session, reg_in: schemas.PatientRegisterRequest) -> tuple[models.Patient, models.User]:
    """Atomic creation of Patient + User account in one transaction."""
    existing = get_user_by_username(db, reg_in.username)
    if existing:
        raise ValueError("Username already registered")

    pid = generate_patient_id(db)
    patient = models.Patient(
        patient_id=pid,
        name=reg_in.full_name,
        date_of_birth=reg_in.date_of_birth,
        gender=reg_in.gender,
        phone=reg_in.phone,
        preferred_language=reg_in.preferred_language or "English"
    )
    db.add(patient)
    db.flush()

    hashed_pwd = get_password_hash(reg_in.password)
    user = models.User(
        username=reg_in.username,
        password_hash=hashed_pwd,
        role="PATIENT",
        patient_id=pid
    )
    db.add(user)
    db.commit()
    db.refresh(patient)
    db.refresh(user)
    return patient, user

def get_patient(db: Session, patient_id: str) -> Optional[models.Patient]:
    return db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()

def list_patients(db: Session, limit: int = 50) -> List[models.Patient]:
    return db.query(models.Patient).order_by(desc(models.Patient.created_at)).limit(limit).all()

# --- Visit Operations ---

def generate_visit_id(db: Session) -> str:
    count = db.query(models.Visit).count() + 1
    return f"VIS-{count:06d}"

def create_visit(db: Session, visit_in: schemas.VisitCreate) -> models.Visit:
    vid = generate_visit_id(db)
    visit = models.Visit(
        visit_id=vid,
        patient_id=visit_in.patient_id,
        doctor_id=visit_in.doctor_id or "DOC-101",
        department=visit_in.department or "General Medicine",
        visit_date=datetime.datetime.utcnow(),
        status="WAITING",
        priority=visit_in.priority or "NORMAL"
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit

def get_visit(db: Session, visit_id: str) -> Optional[models.Visit]:
    return db.query(models.Visit).filter(models.Visit.visit_id == visit_id).first()

def get_patient_visits(db: Session, patient_id: str) -> List[models.Visit]:
    return db.query(models.Visit).filter(models.Visit.patient_id == patient_id).order_by(desc(models.Visit.visit_date)).all()

def get_doctor_queue(db: Session) -> List[models.Visit]:
    """Get active queue for doctor (priority RED/HIGH first)"""
    return db.query(models.Visit).filter(models.Visit.status.in_(["WAITING", "IN_PROGRESS"]))\
        .order_by(
            models.Visit.priority.desc(), # HIGH/EMERGENCY before NORMAL
            models.Visit.visit_date.asc()
        ).all()

def update_visit_status(db: Session, visit_id: str, status: str, priority: str = None) -> Optional[models.Visit]:
    visit = get_visit(db, visit_id)
    if visit:
        visit.status = status
        if priority:
            visit.priority = priority
        db.commit()
        db.refresh(visit)
    return visit

# --- Clinical History Operations ---

def create_or_update_clinical_history(db: Session, history_in: schemas.ClinicalHistoryCreate) -> models.ClinicalHistory:
    existing = db.query(models.ClinicalHistory).filter(models.ClinicalHistory.visit_id == history_in.visit_id).first()
    if existing:
        existing.history_json = history_in.history_json
        existing.source = history_in.source or existing.source
        existing.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(existing)
        ch = existing
    else:
        ch = models.ClinicalHistory(
            visit_id=history_in.visit_id,
            patient_id=history_in.patient_id,
            history_json=history_in.history_json,
            source=history_in.source or "Part1_Engine"
        )
        db.add(ch)
        db.commit()
        db.refresh(ch)

    # Check if triage in history_json dictates visit priority
    triage_info = history_in.history_json.get("triage", {})
    prio = triage_info.get("priority")
    if prio in ["HIGH", "EMERGENCY", "RED"]:
        update_visit_status(db, history_in.visit_id, status="WAITING", priority="HIGH")

    return ch

def get_clinical_history(db: Session, visit_id: str) -> Optional[models.ClinicalHistory]:
    return db.query(models.ClinicalHistory).filter(models.ClinicalHistory.visit_id == visit_id).first()

# --- Document Operations ---

def generate_document_id(db: Session) -> str:
    count = db.query(models.Document).count() + 1
    return f"DOC-{count:06d}"

def create_document(db: Session, doc_in: schemas.DocumentCreate) -> models.Document:
    did = generate_document_id(db)
    doc = models.Document(
        document_id=did,
        patient_id=doc_in.patient_id,
        visit_id=doc_in.visit_id,
        document_type=doc_in.document_type,
        document_date=doc_in.document_date or datetime.datetime.utcnow(),
        raw_text=doc_in.raw_text,
        structured_data=doc_in.structured_data or {},
        ocr_confidence=doc_in.ocr_confidence if doc_in.ocr_confidence is not None else 1.0,
        extraction_confidence=doc_in.extraction_confidence if doc_in.extraction_confidence is not None else 1.0,
        verification_required=doc_in.verification_required or False,
        verified=doc_in.verified if doc_in.verified is not None else True,
        file_reference=doc_in.file_reference
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

def get_patient_documents(db: Session, patient_id: str) -> List[models.Document]:
    return db.query(models.Document).filter(models.Document.patient_id == patient_id).order_by(desc(models.Document.document_date)).all()

def verify_document(db: Session, document_id: str, verified: bool, new_structured_data: dict = None) -> Optional[models.Document]:
    doc = db.query(models.Document).filter(models.Document.document_id == document_id).first()
    if doc:
        doc.verified = verified
        doc.verification_required = False
        if new_structured_data:
            doc.structured_data = new_structured_data
        db.commit()
        db.refresh(doc)
    return doc

# --- Prescription Operations ---

def generate_prescription_id(db: Session) -> str:
    count = db.query(models.Prescription).count() + 1
    return f"RX-{count:06d}"

def create_prescription(db: Session, rx_in: schemas.PrescriptionCreate) -> models.Prescription:
    rx_id = generate_prescription_id(db)
    rx = models.Prescription(
        prescription_id=rx_id,
        patient_id=rx_in.patient_id,
        visit_id=rx_in.visit_id,
        doctor_id=rx_in.doctor_id,
        status="DRAFT"
    )
    db.add(rx)
    db.commit()
    db.refresh(rx)

    for item in rx_in.items:
        p_item = models.PrescriptionItem(
            prescription_id=rx_id,
            medicine_name=item.medicine_name,
            dose=item.dose,
            route=item.route or "Oral",
            frequency=item.frequency,
            duration=item.duration,
            instructions=item.instructions or "After food"
        )
        db.add(p_item)
    db.commit()
    db.refresh(rx)
    return rx

def confirm_prescription(db: Session, prescription_id: str, updated_items: List[schemas.PrescriptionItemCreate] = None) -> Optional[models.Prescription]:
    rx = db.query(models.Prescription).filter(models.Prescription.prescription_id == prescription_id).first()
    if not rx:
        return None

    if updated_items is not None:
        db.query(models.PrescriptionItem).filter(models.PrescriptionItem.prescription_id == prescription_id).delete()
        for item in updated_items:
            p_item = models.PrescriptionItem(
                prescription_id=prescription_id,
                medicine_name=item.medicine_name,
                dose=item.dose,
                route=item.route or "Oral",
                frequency=item.frequency,
                duration=item.duration,
                instructions=item.instructions or "After food"
            )
            db.add(p_item)

    rx.status = "FINAL"
    db.commit()
    db.refresh(rx)
    return rx

def get_patient_prescriptions(db: Session, patient_id: str) -> List[models.Prescription]:
    return db.query(models.Prescription).filter(models.Prescription.patient_id == patient_id).order_by(desc(models.Prescription.created_at)).all()
