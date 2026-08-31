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


# ── TEST 4: Explicit H/L/# Flag Preserved ─────────────────────────────────────
def test_explicit_flags():
    status, flag = DeterministicMedicalValidator.compute_status_and_flag("0.86", "0.90-1.30", explicit_flag="#")
    assert status == "LOW"
    assert flag == "#"

    status_h, flag_h = DeterministicMedicalValidator.compute_status_and_flag("150", "70-140", explicit_flag="H")
    assert status_h == "HIGH"
    assert flag_h == "H"


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
    assert "Analyzer" in reason or "validation" in reason or "percentile" in reason


# ── TEST 8: Patient Name Followed by Age on Same Line ─────────────────────────
def test_patient_name_and_age_separation():
    raw_patient = {"patient_name": "Ria Age : 19", "age": ""}
    cleaned = DeterministicMedicalValidator.clean_patient_metadata(raw_patient)
    assert cleaned["patient_name"] == "Ria"

    # From raw OCR line
    cleaned_ocr = DeterministicMedicalValidator.clean_patient_metadata({}, full_ocr_text="Name : Ria Age : FC\nRegistration No Sl Lab No : a")
    assert cleaned_ocr["patient_name"] == "Ria"
    assert cleaned_ocr["age"] == "FC"
    assert cleaned_ocr["registration_no"] == "Sl"


# ── TEST 9: OCR-Corrupted Test Name Correction ────────────────────────────────
def test_ocr_spelling_correction():
    corrected = DeterministicMedicalValidator.correct_test_name("roponin-I High sensitivity (hs -TnI)")
    assert corrected.startswith("Troponin-I")

    corrected2 = DeterministicMedicalValidator.correct_test_name("Haemoglobi (Photometric)")
    assert "Haemoglobin" in corrected2


# ── TEST 10: Multiple Laboratory Sections Assignment ──────────────────────────
def test_multiple_laboratory_sections():
    raw_ocr = """
    RENAL PANEL - I
    Plasma GLUCOSE- Random (Hexokinase) 78 mg/dl [70-140]
    
    Troponin-I - High sensitive ( hs - Troponin I)
    roponin-I High sensitivity (hs -TnI) 1.30 ng/L [<17.50]
    
    COMPLETE BLOOD COUNT (Coulter Principle)
    WBC Count (TC) (Coulter Principle) 8800 /cu.mm [4400-11000]
    """
    validated = DeterministicMedicalValidator.validate_and_normalize({"document_type": "LAB_REPORT", "tests": []}, full_ocr_text=raw_ocr)
    tests = validated["tests"]
    assert len(tests) == 3
    assert tests[0]["section"] == "RENAL PANEL - I"
    assert tests[1]["section"] == "BIOCHEMISTRY / CARDIAC MARKERS"
    assert tests[2]["section"] == "HAEMATOLOGY / COMPLETE BLOOD COUNT"


# ── TEST 11: Missing Reference Range (Status = UNKNOWN) ───────────────────────
def test_missing_reference_range():
    status, flag = DeterministicMedicalValidator.compute_status_and_flag("45.2", "")
    assert status == "UNKNOWN"
    assert flag == ""


# ── TEST 12: Duplicate Headers & Pagination ───────────────────────────────────
def test_pagination_and_headers_exclusion():
    is_bad1, _ = DeterministicMedicalValidator.is_non_test("Page 1 of 3", "")
    is_bad2, _ = DeterministicMedicalValidator.is_non_test("Page 2 of 3", "")
    is_bad3, _ = DeterministicMedicalValidator.is_non_test("END OF REPORT", "")
    assert is_bad1 is True
    assert is_bad2 is True
    assert is_bad3 is True


# ── TEST 13: Disclaimer Containing Numbers ────────────────────────────────────
def test_disclaimer_containing_numbers():
    disc_text = "eGFR which is primarily based on Serum Creatinine is a derivation of CKD-EPI 2009 equation normalized tol.73 sq.m"
    is_bad, _ = DeterministicMedicalValidator.is_non_test(disc_text, "2009")
    assert is_bad is True


# ── TEST 14: Publication Date & Citation Containing Numbers ──────────────────
def test_publication_citation_exclusion():
    citation = "Clin Biochem. 2020 May;79:48-53. doi: 10.1016/j.clinbiochem.2020.02.005. Epub 2020 Feb 12. PMID: 32059836."
    is_bad, _ = DeterministicMedicalValidator.is_non_test(citation, "2020")
    assert is_bad is True


# ── TEST 15: Registration Number / Lab No Exclusion from Tests ────────────────
def test_registration_number_exclusion():
    reg_line = "Registration No Sl Lab No : a"
    is_bad, _ = DeterministicMedicalValidator.is_non_test(reg_line)
    # Shouldn't parse as a lab test
    cleaned = DeterministicMedicalValidator.clean_patient_metadata({}, full_ocr_text=reg_line)
    assert cleaned["registration_no"] == "Sl"
    assert cleaned["lab_no"] == "a"


# ── TEST 16: Analyzer/Instrument Description Containing Numerical Values ──────
def test_instrument_note_exclusion():
    note_line = "\" <17.5 ng/L is the upper reference Limit for (hs -TnI)."
    is_bad, _ = DeterministicMedicalValidator.is_non_test(note_line, "17.5")
    assert is_bad is True


# ── TEST 17: Validation Counts Match Array Lengths Dynamically ────────────────
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


# ── TEST 18: End-to-End Extraction with Sample PDF Report ─────────────────────
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

    # 2. Verify all genuine tests are extracted (>= 25 tests)
    assert len(tests) >= 25

    # 3. Verify counts match arrays exactly
    val = structured["validation"]
    assert val["total_tests"] == len(tests)
    assert val["excluded_non_test_items"] == len(excluded)

    # 4. Verify patient name is not "Ria Age"
    patient = structured["patient"]
    assert patient["patient_name"] == "Ria"
