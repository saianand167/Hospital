import os
import pytest
from pathlib import Path
from app.services.document_processing.pipeline import (
    DeterministicMedicalValidator,
    DocumentOCRProvider,
    StructuredDataExtractor,
    DocumentProcessingPipeline
)

# ── TEST 1: Normal Laboratory Row ─────────────────────────────────────────────
def test_normal_laboratory_row():
    status, flag = DeterministicMedicalValidator.compute_status_and_flag("78", "70-140")
    assert status == "NORMAL"
    assert flag == ""


# ── TEST 2: High Result ───────────────────────────────────────────────────────
def test_high_result():
    status, flag = DeterministicMedicalValidator.compute_status_and_flag("165.0", "70-140")
    assert status == "HIGH"
    assert flag == "#"


# ── TEST 3: Low Result ────────────────────────────────────────────────────────
def test_low_result():
    status, flag = DeterministicMedicalValidator.compute_status_and_flag("0.86", "0.90-1.30")
    assert status == "LOW"
    assert flag == "#"


# ── TEST 4: Explicit # Abnormal Flag Preserved ────────────────────────────────
def test_explicit_abnormal_flag():
    status, flag = DeterministicMedicalValidator.compute_status_and_flag("0.86", "0.90-1.30", explicit_flag="#")
    assert status == "LOW"
    assert flag == "#"


# ── TEST 5: DOI inside Reference Section (Must NOT Become Test) ───────────────
def test_doi_exclusion():
    is_bad, reason = DeterministicMedicalValidator.is_non_test("doi", "10.1016/j.clinbiochem.2020.02.005")
    assert is_bad is True
    assert "DOI" in reason or "academic" in reason.lower()


# ── TEST 6: PMID inside Reference Section (Must NOT Become Test) ──────────────
def test_pmid_exclusion():
    is_bad, reason = DeterministicMedicalValidator.is_non_test("PMID", "32059836")
    assert is_bad is True
    assert "PubMed" in reason or "PMID" in reason


# ── TEST 7: Research Article Title Containing Numbers (Must NOT Become Test) ─
def test_research_article_exclusion():
    is_bad, reason = DeterministicMedicalValidator.is_non_test(
        "Evaluation of the new Beckman Coulter Access hsTnI: 99th percentile",
        "99"
    )
    assert is_bad is True


# ── TEST 8: Patient Name Followed by Age (Separated Correctly) ────────────────
def test_patient_name_and_age_separation():
    raw_patient = {"patient_name": "Ria Age : 19", "age": "19"}
    cleaned = DeterministicMedicalValidator.clean_patient_metadata(raw_patient)
    assert cleaned["patient_name"] == "Ria"
    assert cleaned["age"] == "19"


# ── TEST 9: OCR Spelling Error Correction ─────────────────────────────────────
def test_ocr_spelling_correction():
    corrected = DeterministicMedicalValidator.correct_test_name("roponin-I High sensitivity")
    assert corrected == "Troponin-I High sensitivity"

    corrected2 = DeterministicMedicalValidator.correct_test_name("Haemoglobi (Photometric)")
    assert "Haemoglobin" in corrected2


# ── TEST 10: Multiple Laboratory Sections Assignment ──────────────────────────
def test_multiple_laboratory_sections():
    raw_data = {
        "document_type": "LAB_REPORT",
        "patient": {"patient_name": "Rajesh Kumar"},
        "tests": [
            {
                "section": "RENAL PANEL - I",
                "test_name": "Plasma GLUCOSE- Random (Hexokinase)",
                "result_value": "78",
                "unit": "mg/dl",
                "reference_range": "70-140",
                "confidence": "HIGH"
            },
            {
                "section": "BIOCHEMISTRY",
                "test_name": "Troponin-I High sensitivity (hs -TnI)",
                "result_value": "1.30",
                "unit": "ng/L",
                "reference_range": "<17.50",
                "confidence": "HIGH"
            },
            {
                "section": "HAEMATOLOGY",
                "test_name": "WBC Count (TC) (Coulter Principle)",
                "result_value": "8800",
                "unit": "/cu.mm",
                "reference_range": "4400-11000",
                "confidence": "HIGH"
            }
        ],
        "excluded_items": []
    }
    validated = DeterministicMedicalValidator.validate_and_normalize(raw_data)
    tests = validated["tests"]
    assert len(tests) == 3
    assert tests[0]["section"] == "RENAL PANEL - I"
    assert tests[1]["section"] == "BIOCHEMISTRY"
    assert tests[2]["section"] == "HAEMATOLOGY"


# ── TEST 11: Validation Counts Match Array Lengths Dynamically ────────────────
def test_validation_counts_calculation():
    raw_data = {
        "document_type": "LAB_REPORT",
        "patient": {},
        "tests": [
            {"test_name": "Test A", "result_value": "10", "unit": "mg/dL", "confidence": "HIGH"},
            {"test_name": "Test B", "result_value": "20", "unit": "mg/dL", "confidence": "MEDIUM"},
            {"test_name": "doi: 10.1016/sample", "result_value": "10.1016"}  # Should be excluded
        ],
        "excluded_items": []
    }
    validated = DeterministicMedicalValidator.validate_and_normalize(raw_data)
    val_stats = validated["validation"]
    
    assert val_stats["total_tests"] == 2
    assert val_stats["high_confidence_tests"] == 1
    assert val_stats["medium_confidence_tests"] == 1
    assert val_stats["low_confidence_tests"] == 0
    assert val_stats["excluded_non_test_items"] == 1
    assert len(validated["tests"]) == 2
    assert len(validated["excluded_items"]) == 1


# ── TEST 12: Missing Reference Range (Status = UNKNOWN) ───────────────────────
def test_missing_reference_range():
    status, flag = DeterministicMedicalValidator.compute_status_and_flag("45.2", "")
    assert status == "UNKNOWN"
    assert flag == ""


# ── TEST 13: End-to-End Extraction with Sample PDF Report ─────────────────────
def test_end_to_end_sample_report():
    sample_pdf_path = Path(__file__).resolve().parents[3] / "uploads" / "PAT-000009_c7bf4265.pdf"
    if not sample_pdf_path.exists():
        pytest.skip(f"Sample PDF not found at {sample_pdf_path}")

    with open(sample_pdf_path, "rb") as f:
        pdf_bytes = f.read()

    result = DocumentProcessingPipeline.process_upload(
        file_bytes=pdf_bytes,
        filename="investigationlabreports.pdf",
        patient_id="PAT-000009",
        visit_id="VIS-000001",
        document_type="LAB_REPORT"
    )

    assert result["document_type"] == "LAB_REPORT"
    assert result["ocr_confidence"] >= 0.70
    structured = result["structured_data"]
    tests = structured["tests"]
    excluded = structured["excluded_items"]

    # 1. Verify research references / DOI / PMID are NOT in tests
    for t in tests:
        assert "doi" not in t["test_name"].lower()
        assert "pmid" not in t["test_name"].lower()
        assert "beckman coulter" not in t["test_name"].lower()
        assert "biomarker study group" not in t["test_name"].lower()

    # 2. Verify genuine tests are extracted across sections
    assert len(tests) >= 10

    # 3. Verify counts match
    val = structured["validation"]
    assert val["total_tests"] == len(tests)
    assert val["excluded_non_test_items"] == len(excluded)
