"""
Validation Agent — Field-level confidence and verification flagging.

Validates extraction results across all document types.
Sets requires_verification when:
  - Overall confidence is low
  - Any prescription medication has low confidence
  - Lab extraction returned empty sections
  - Document type is UNKNOWN
"""
from typing import Dict, Any, Tuple
from app.schemas.documents import DocumentType


HIGH_CONFIDENCE_THRESHOLD = 0.80
LOW_CONFIDENCE_THRESHOLD  = 0.55


class ValidationAgent:
    @staticmethod
    def validate(
        document_type: DocumentType,
        extraction_data: Dict[str, Any],
        ocr_confidence: float,
        classification_confidence: float,
    ) -> Tuple[float, bool, str]:
        """
        Returns (extraction_confidence, requires_verification, status_message).
        status: success | partial | verification_required | failed
        """

        # 1. Classification too uncertain
        if document_type == DocumentType.UNKNOWN or classification_confidence < LOW_CONFIDENCE_THRESHOLD:
            return 0.40, True, "verification_required"

        # 2. LLM extraction returned nothing useful
        if not extraction_data or "_extraction_note" in extraction_data:
            note = extraction_data.get("_extraction_note", "") if extraction_data else ""
            if "failed" in note.lower():
                return 0.0, True, "failed"
            return 0.40, True, "verification_required"

        # 3. Type-specific checks
        if document_type == DocumentType.LAB_REPORT:
            sections = extraction_data.get("sections", [])
            total_tests = sum(len(s.get("tests", [])) for s in sections)
            if total_tests == 0:
                return 0.35, True, "verification_required"
            # Check for any tests with None values
            null_vals = sum(
                1 for s in sections for t in s.get("tests", []) if t.get("value") is None
            )
            null_ratio = null_vals / max(total_tests, 1)
            if null_ratio > 0.5:
                conf = 0.60
                return conf, True, "partial"
            conf = max(0.70, 1.0 - null_ratio) * min(ocr_confidence + 0.05, 1.0)
            return round(min(conf, 0.97), 3), False, "success"

        elif document_type == DocumentType.PRESCRIPTION:
            meds = extraction_data.get("medications", [])
            if not meds:
                return 0.30, True, "verification_required"
            # Critical field verification: strictly require verification if drug name/dose confidence < 0.80 or missing
            critical_missing_or_low = [
                m for m in meds 
                if not m.get("name") or not m.get("dose") or m.get("confidence", 1.0) < 0.80
            ]
            has_verification_needed = any(m.get("needs_verification") for m in meds)
            if critical_missing_or_low or has_verification_needed or ocr_confidence < 0.75:
                return 0.65, True, "verification_required"
            return 0.88, False, "success"

        elif document_type == DocumentType.DISCHARGE_SUMMARY:
            has_content = any([
                extraction_data.get("diagnoses"),
                extraction_data.get("admission_date"),
                extraction_data.get("hospital_course"),
            ])
            if not has_content:
                return 0.40, True, "verification_required"
            return 0.82, False, "success"

        elif document_type == DocumentType.IMAGING_REPORT:
            has_content = any([
                extraction_data.get("findings"),
                extraction_data.get("impression"),
            ])
            if not has_content:
                return 0.40, True, "verification_required"
            return 0.85, False, "success"

        elif document_type == DocumentType.PATHOLOGY_REPORT:
            has_content = any([
                extraction_data.get("microscopic_findings"),
                extraction_data.get("pathological_diagnosis"),
            ])
            if not has_content:
                return 0.40, True, "verification_required"
            return 0.83, False, "success"

        elif document_type == DocumentType.OPD_NOTE:
            has_content = any([
                extraction_data.get("chief_complaint"),
                extraction_data.get("assessment"),
                extraction_data.get("plan"),
            ])
            if not has_content:
                return 0.40, True, "verification_required"
            return 0.80, False, "success"

        # Other/Unknown
        return 0.50, True, "verification_required"
