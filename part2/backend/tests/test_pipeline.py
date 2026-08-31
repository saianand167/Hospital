"""
Part 2 Test Suite — SIH26047 MediKiosk
Tests: Classification, Extraction, Validation, API Pipeline
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agents.classifier_agent import DocumentClassifier
from app.schemas.documents import DocumentType
from app.agents.validation_agent import ValidationAgent

# ─── Test 1: Lab Report Classification ───────────────────────────────────────
def test_lab_report_classified_correctly():
    """The investigationlabreports.pdf bug — must NOT classify as PRESCRIPTION."""
    text = """
    CLINICAL LABORATORY REPORT
    Renal Panel
    Glucose - Random: 78 mg/dL  Reference Range: 70-140
    BUN: 9.81 mg/dL  Reference Range: 6-20
    Serum Creatinine: 0.86 mg/dL  Reference Range: 0.90-1.30
    eGFR: 115.5 mL/min/1.73m2
    Sodium: 141 mEq/L  Reference Range: 136-145
    Potassium: 4.4 mEq/L  Reference Range: 3.5-5.1
    Chloride: 104 mEq/L
    Bicarbonate: 24 mEq/L
    Urea: 20.9 mg/dL

    hs-Troponin I: <0.006 ng/mL  Reference Range: <0.034
    
    Complete Blood Count
    WBC: 8800 cells/uL  Reference Range: 4500-11000
    RBC: 5.16 million/uL
    Hemoglobin: 15.1 g/dL  Reference Range: 13.0-17.0
    Hematocrit: 44.3%
    MCV: 82.1 fL  Reference Range: 83.0-101.0
    MCH: 29.3 pg
    MCHC: 34.1 g/dL
    Platelets: 216 K/uL
    RDW: 14.5%
    MPV: 8.7 fL
    """
    doc_type, confidence = DocumentClassifier.classify(text, "investigationlabreports.pdf")
    assert doc_type == DocumentType.LAB_REPORT, f"Expected LAB_REPORT, got {doc_type}"
    assert confidence >= 0.70, f"Confidence too low: {confidence}"

# ─── Test 2: Prescription ────────────────────────────────────────────────────
def test_prescription_classified_correctly():
    text = """
    Rx Prescription
    Dr. Sharma MD
    Patient: John Doe  Date: 2026-08-01
    1. Tab. Paracetamol 500mg - Once daily after food - 5 days
    2. Cap. Amoxicillin 250mg - Twice daily before food - 7 days
    3. Syrup Cough Relief 10ml - Three times daily - 3 days
    Signature of Doctor
    """
    doc_type, confidence = DocumentClassifier.classify(text, "prescription.pdf")
    assert doc_type == DocumentType.PRESCRIPTION, f"Expected PRESCRIPTION, got {doc_type}"

# ─── Test 3: Discharge Summary ────────────────────────────────────────────────
def test_discharge_summary_classified_correctly():
    text = """
    DISCHARGE SUMMARY
    Date of Admission: 2026-07-20   Date of Discharge: 2026-07-25
    Hospital Course: Patient admitted with chest pain. 
    Diagnosis: Acute Myocardial Infarction
    Procedures Performed: Coronary angioplasty
    Condition on Discharge: Stable
    Follow up with cardiologist in 2 weeks
    """
    doc_type, confidence = DocumentClassifier.classify(text, "discharge.pdf")
    assert doc_type == DocumentType.DISCHARGE_SUMMARY, f"Expected DISCHARGE_SUMMARY, got {doc_type}"

# ─── Test 4: Imaging Report ───────────────────────────────────────────────────
def test_imaging_report_classified_correctly():
    text = """
    RADIOLOGY REPORT
    Modality: MRI Brain
    Clinical Indication: Headache
    Findings: No focal lesion. No midline shift. Ventricles normal in size.
    Impression: Normal MRI of the brain.
    Radiologist: Dr. Patel
    """
    doc_type, confidence = DocumentClassifier.classify(text, "mri_brain.pdf")
    assert doc_type == DocumentType.IMAGING_REPORT, f"Expected IMAGING_REPORT, got {doc_type}"

# ─── Test 5: Pathology Report ─────────────────────────────────────────────────
def test_pathology_report_classified_correctly():
    text = """
    HISTOPATHOLOGY REPORT
    Specimen Received: Breast biopsy
    Gross Examination: 2cm mass, firm, white-grey
    Microscopic Examination: Invasive ductal carcinoma
    Pathological Diagnosis: Malignant neoplasm
    Pathologist: Dr. Rao
    """
    doc_type, confidence = DocumentClassifier.classify(text, "biopsy_report.pdf")
    assert doc_type == DocumentType.PATHOLOGY_REPORT, f"Expected PATHOLOGY_REPORT, got {doc_type}"

# ─── Test 6: Unknown / low quality ───────────────────────────────────────────
def test_unknown_for_ambiguous_text():
    text = "handwritten scribble qwerty abc xyz"
    doc_type, confidence = DocumentClassifier.classify(text, "unknown.pdf")
    # Should be UNKNOWN with low confidence (won't match any keywords)
    assert confidence < 0.70, f"Expected low confidence, got {confidence}"

# ─── Test 7: Lab report NOT classified as prescription ────────────────────────
def test_lab_report_not_prescription_due_to_mg():
    """Core regression test: mg/dL in lab reports must NOT trigger prescription."""
    text = """
    Test Name          Result       Reference
    Hemoglobin         14.5 g/dL    13.0 - 17.0
    Serum Creatinine   0.9 mg/dL    0.7 - 1.2
    Glucose            95 mg/dL     70 - 100
    Sodium             138 mEq/L    136 - 145
    Reference Range: values shown above
    """
    doc_type, confidence = DocumentClassifier.classify(text, "lab.pdf")
    assert doc_type == DocumentType.LAB_REPORT, (
        f"REGRESSION: mg/dL in lab report caused wrong type {doc_type}"
    )

# ─── Test 8: Abnormal detection ───────────────────────────────────────────────
def test_abnormal_detection_below_range():
    from app.agents.extraction_agent import _check_abnormal
    flag, interp = _check_abnormal(0.86, "0.90-1.30")
    assert flag is True   # below range
    assert interp["status"] == "LOW"

def test_abnormal_detection_normal():
    from app.agents.extraction_agent import _check_abnormal
    flag, interp = _check_abnormal(1.0, "0.90-1.30")
    assert flag is False   # within range
    assert interp["status"] == "NORMAL"

def test_abnormal_detection_no_range():
    from app.agents.extraction_agent import _check_abnormal
    flag, interp = _check_abnormal(1.0, None)
    assert flag is None   # no reference → None
    assert interp["status"] == "UNKNOWN"

# ─── Test 9: Validation — empty lab report ────────────────────────────────────
def test_validation_empty_lab_triggers_verification():
    conf, requires_verify, status = ValidationAgent.validate(
        DocumentType.LAB_REPORT, {"sections": []}, 0.85, 0.90
    )
    assert requires_verify is True
    assert status == "verification_required"

# ─── Test 10: Validation — good lab report ────────────────────────────────────
def test_validation_good_lab_succeeds():
    data = {
        "sections": [{
            "section_name": "CBC",
            "tests": [
                {"name": "WBC", "value": 8.5, "unit": "K/uL", "reference_range": "4.5-11.0", "abnormal": False},
                {"name": "Hemoglobin", "value": 14.5, "unit": "g/dL", "reference_range": "13-17", "abnormal": False},
            ]
        }]
    }
    conf, requires_verify, status = ValidationAgent.validate(
        DocumentType.LAB_REPORT, data, 0.92, 0.95
    )
    assert status == "success"
    assert not requires_verify
    assert conf > 0.70

# ─── Test 11: Validation — UNKNOWN always flags verification ──────────────────
def test_unknown_type_always_requires_verification():
    conf, requires_verify, status = ValidationAgent.validate(
        DocumentType.UNKNOWN, {}, 0.90, 0.40
    )
    assert requires_verify is True

# ─── Test 12: OPD note ───────────────────────────────────────────────────────
def test_opd_note_classified_correctly():
    text = """
    OPD Note
    Chief Complaint: Fever for 3 days
    History of Present Illness: Patient presents with high-grade fever
    Objective: Temp 102F, pulse 92
    Assessment: Viral fever
    Plan: Tab Paracetamol, rest, plenty of fluids
    Follow-up: After 3 days
    """
    doc_type, confidence = DocumentClassifier.classify(text, "opd_note.pdf")
    assert doc_type in [DocumentType.OPD_NOTE, DocumentType.PRESCRIPTION], \
        f"Expected OPD_NOTE or PRESCRIPTION, got {doc_type}"
