import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from database.connection import Base

try:
    from pgvector.sqlalchemy import Vector
    _VECTOR_TYPE = Vector(384)
except Exception:
    _VECTOR_TYPE = Text


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    department = Column(String(100), default="General Medicine")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    visits = relationship("Visit", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")


class Pharmacist(Base):
    __tablename__ = "pharmacists"

    id = Column(Integer, primary_key=True, index=True)
    pharmacist_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(50), unique=True, index=True, nullable=False)  # PAT-XXXXXX
    name = Column(String(100), nullable=False)
    date_of_birth = Column(String(20), nullable=True)
    gender = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    preferred_language = Column(String(50), default="English")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    visits = relationship("Visit", back_populates="patient", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")
    clinical_histories = relationship("ClinicalHistory", back_populates="patient", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="patient", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="patient", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # PATIENT, DOCTOR, PHARMACIST, STAFF
    patient_id = Column(String(50), ForeignKey("patients.patient_id"), nullable=True)
    doctor_id = Column(String(50), ForeignKey("doctors.doctor_id"), nullable=True)
    pharmacist_id = Column(String(50), ForeignKey("pharmacists.pharmacist_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(String(50), unique=True, index=True, nullable=False)    # VIS-XXXXXX
    patient_id = Column(String(50), ForeignKey("patients.patient_id"), nullable=False, index=True)
    doctor_id = Column(String(50), ForeignKey("doctors.doctor_id"), nullable=True, index=True)
    department = Column(String(100), default="General Medicine")
    visit_date = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    status = Column(String(20), default="WAITING")  # WAITING, IN_PROGRESS, COMPLETED
    priority = Column(String(20), default="NORMAL")  # NORMAL, HIGH, EMERGENCY
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="visits")
    doctor = relationship("Doctor", back_populates="visits")
    clinical_history = relationship("ClinicalHistory", back_populates="visit", uselist=False)
    documents = relationship("Document", back_populates="visit")
    prescriptions = relationship("Prescription", back_populates="visit")


class ClinicalHistory(Base):
    __tablename__ = "clinical_histories"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(String(50), ForeignKey("visits.visit_id"), unique=True, nullable=False, index=True)
    patient_id = Column(String(50), ForeignKey("patients.patient_id"), nullable=False, index=True)
    history_json = Column(JSONB, nullable=False, default=dict)
    source = Column(String(50), default="Part1_Engine")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    visit = relationship("Visit", back_populates="clinical_history")
    patient = relationship("Patient", back_populates="clinical_histories")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(50), unique=True, index=True, nullable=False)  # DOC-XXXXXX
    patient_id = Column(String(50), ForeignKey("patients.patient_id"), nullable=False, index=True)
    visit_id = Column(String(50), ForeignKey("visits.visit_id"), nullable=True, index=True)
    document_type = Column(String(50), nullable=False)
    document_date = Column(DateTime, default=datetime.datetime.utcnow)
    raw_text = Column(Text, nullable=True)
    structured_data = Column(JSONB, nullable=True, default=dict)
    ocr_confidence = Column(Float, default=1.0)
    extraction_confidence = Column(Float, default=1.0)
    verification_required = Column(Boolean, default=False)
    verified = Column(Boolean, default=True)
    file_reference = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="documents")
    visit = relationship("Visit", back_populates="documents")
    embeddings = relationship("Embedding", back_populates="document", cascade="all, delete-orphan")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(String(50), unique=True, index=True, nullable=False)
    patient_id = Column(String(50), ForeignKey("patients.patient_id"), nullable=False, index=True)
    visit_id = Column(String(50), ForeignKey("visits.visit_id"), nullable=False, index=True)
    doctor_id = Column(String(50), ForeignKey("doctors.doctor_id"), nullable=False, index=True)
    status = Column(String(20), default="DRAFT")  # DRAFT, FINAL, CANCELLED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="prescriptions")
    visit = relationship("Visit", back_populates="prescriptions")
    doctor = relationship("Doctor", back_populates="prescriptions")
    items = relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(String(50), ForeignKey("prescriptions.prescription_id"), nullable=False, index=True)
    medicine_name = Column(String(100), nullable=False)
    dose = Column(String(50), nullable=False)
    route = Column(String(50), default="Oral")
    frequency = Column(String(50), nullable=False)
    duration = Column(String(50), nullable=False)
    instructions = Column(String(255), default="After food")

    prescription = relationship("Prescription", back_populates="items")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    target_id = Column(String(50), nullable=True, index=True)
    details = Column(JSONB, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(50), ForeignKey("patients.patient_id"), index=True, nullable=False)
    visit_id = Column(String(50), ForeignKey("visits.visit_id"), index=True, nullable=True)
    document_id = Column(String(50), ForeignKey("documents.document_id"), index=True, nullable=True)
    source_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(_VECTOR_TYPE, nullable=True)

    patient = relationship("Patient", back_populates="embeddings")
    document = relationship("Document", back_populates="embeddings")
