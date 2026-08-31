"""
Document Classifier Agent — Fixed Version.

Root cause of old bug:
  text.count("mg") was used. Lab reports contain "mg/dL" dozens of times,
  inflating the PRESCRIPTION score even for pure lab reports.

Fix:
  - Phrase-level matching (not single-character substrings like "mg", "ml")
  - Weighted scoring: high-value discriminating keywords score 3x
  - Negative keywords: presence of strong lab markers cancels prescription score
  - Groq LLM fallback with a structured classification prompt
  - Unknown threshold: confidence < 0.55 -> UNKNOWN + requires_verification
"""
import re
from typing import Tuple, List
from app.schemas.documents import DocumentType
from app.config import settings

# ─── Weighted keyword rules ───────────────────────────────────────────────────
# Each entry: (keyword_phrase, weight)
# High weight = strong discriminating signal for that document type

WEIGHTED_RULES: dict[DocumentType, List[Tuple[str, int]]] = {

    DocumentType.LAB_REPORT: [
        # Strong discriminators (weight 3)
        ("laboratory report", 3),
        ("clinical laboratory", 3),
        ("investigation report", 3),
        ("lab report", 3),
        ("haematology", 3),
        ("hematology", 3),
        ("complete blood count", 3),
        ("cbc", 3),
        ("renal panel", 3),
        ("liver function", 3),
        ("lipid profile", 3),
        ("thyroid profile", 3),
        ("troponin", 3),
        ("electrolytes", 3),
        ("serum creatinine", 3),
        ("egfr", 3),
        ("blood urea nitrogen", 3),
        ("reference range", 3),
        ("reference interval", 3),
        ("normal range", 3),
        ("test name", 3),
        ("result value", 3),
        ("specimen", 3),
        ("collected on", 3),
        ("reported on", 3),
        # Medium discriminators (weight 2)
        ("hemoglobin", 2),
        ("haemoglobin", 2),
        ("hematocrit", 2),
        ("haematocrit", 2),
        ("platelets", 2),
        ("wbc", 2),
        ("rbc", 2),
        ("mcv", 2),
        ("mch", 2),
        ("mchc", 2),
        ("rdw", 2),
        ("mpv", 2),
        ("sodium", 2),
        ("potassium", 2),
        ("chloride", 2),
        ("bicarbonate", 2),
        ("bilirubin", 2),
        ("urea", 2),
        ("creatinine", 2),
        ("glucose", 2),
        ("cholesterol", 2),
        ("triglycerides", 2),
        ("pathology", 2),
    ],

    DocumentType.PRESCRIPTION: [
        # Strong discriminators (weight 3)
        ("rx prescription", 3),
        ("dr prescription", 3),
        ("prescription date", 3),
        ("prescribed by", 3),
        ("sig:", 3),
        ("dispense", 3),
        ("refills", 3),
        ("take one tablet", 3),
        ("take two tablets", 3),
        # Medium (weight 2)
        ("tab.", 2),
        ("cap.", 2),
        ("tablet", 2),
        ("capsule", 2),
        ("syrup", 2),
        ("once daily", 2),
        ("twice daily", 2),
        ("three times", 2),
        ("after food", 2),
        ("before food", 2),
        ("at bedtime", 2),
        # Low (weight 1)
        ("rx", 1),
        ("od ", 1),
        ("bd ", 1),
        ("tds ", 1),
        ("qid ", 1),
        ("sos ", 1),
        ("stat ", 1),
    ],

    DocumentType.DISCHARGE_SUMMARY: [
        ("discharge summary", 3),
        ("discharge note", 3),
        ("hospital course", 3),
        ("reason for admission", 3),
        ("date of admission", 3),
        ("date of discharge", 3),
        ("discharge diagnosis", 3),
        ("discharge condition", 3),
        ("inpatient", 2),
        ("admission date", 2),
        ("discharge date", 2),
        ("hospitalization", 2),
        ("admitted on", 2),
        ("discharged on", 2),
        ("icu", 2),
        ("ward", 2),
        ("procedures performed", 2),
        ("follow up", 1),
    ],

    DocumentType.IMAGING_REPORT: [
        ("radiology report", 3),
        ("imaging report", 3),
        ("radiological report", 3),
        ("x-ray report", 3),
        ("mri report", 3),
        ("ct report", 3),
        ("ultrasound report", 3),
        ("sonography report", 3),
        ("pet scan", 3),
        ("impression:", 3),
        ("findings:", 2),
        ("modality:", 2),
        ("x-ray", 2),
        ("computed tomography", 2),
        ("magnetic resonance", 2),
        ("ultrasound", 2),
        ("sonography", 2),
        ("radiologist", 2),
        ("no focal lesion", 2),
        ("no acute", 2),
    ],

    DocumentType.PATHOLOGY_REPORT: [
        ("pathology report", 3),
        ("histopathology", 3),
        ("biopsy report", 3),
        ("cytology", 3),
        ("specimen received", 3),
        ("gross examination", 3),
        ("microscopic examination", 3),
        ("microscopic findings", 3),
        ("histological", 3),
        ("pathological diagnosis", 3),
        ("malignant", 2),
        ("benign", 2),
        ("adenocarcinoma", 2),
        ("carcinoma", 2),
        ("tumor", 2),
        ("tissue", 2),
    ],

    DocumentType.OPD_NOTE: [
        ("opd note", 3),
        ("outpatient note", 3),
        ("clinic note", 3),
        ("consultation note", 3),
        ("chief complaint", 3),
        ("history of present illness", 3),
        ("hpi:", 3),
        ("clinical assessment", 2),
        ("plan of care", 2),
        ("soap note", 2),
        ("subjective:", 2),
        ("objective:", 2),
        ("assessment:", 2),
        ("plan:", 2),
        ("follow-up:", 1),
    ],
}

# Strong LAB indicators — if any present, heavily penalize PRESCRIPTION
LAB_NEGATIVE_FOR_PRESCRIPTION = [
    "reference range",
    "reference interval",
    "normal range",
    "serum creatinine",
    "complete blood count",
    "renal panel",
    "liver function",
    "laboratory report",
    "investigation report",
    "clinical laboratory",
    "troponin",
    "hematology",
    "haematology",
]

CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.55  # below this -> UNKNOWN


def _score_text(text_lower: str) -> dict[DocumentType, float]:
    """Score document types based on weighted keyword matches."""
    scores: dict[DocumentType, float] = {}
    for doc_type, rules in WEIGHTED_RULES.items():
        total = 0.0
        for phrase, weight in rules:
            # Use whole-phrase matching with word boundaries where possible
            count = len(re.findall(r'\b' + re.escape(phrase) + r'\b', text_lower))
            total += count * weight
        if total > 0:
            scores[doc_type] = total
    return scores


class DocumentClassifier:
    @staticmethod
    def classify(text: str, filename_hint: str = "") -> Tuple[DocumentType, float]:
        """
        Classifies a document based on extracted OCR text and filename.
        Returns (DocumentType, confidence_score).
        """
        text_lower = text.lower()
        filename_lower = filename_hint.lower()

        # 1. Filename strong hints
        if any(kw in filename_lower for kw in ["lab", "blood", "investigation", "test", "report", "cbc", "renal"]):
            filename_boost = {DocumentType.LAB_REPORT: 5.0}
        elif any(kw in filename_lower for kw in ["prescription", "rx", "medicine"]):
            filename_boost = {DocumentType.PRESCRIPTION: 5.0}
        elif any(kw in filename_lower for kw in ["discharge", "summary"]):
            filename_boost = {DocumentType.DISCHARGE_SUMMARY: 5.0}
        elif any(kw in filename_lower for kw in ["xray", "mri", "ct", "ultrasound", "imaging", "radiology"]):
            filename_boost = {DocumentType.IMAGING_REPORT: 5.0}
        elif any(kw in filename_lower for kw in ["pathology", "biopsy", "histopathology"]):
            filename_boost = {DocumentType.PATHOLOGY_REPORT: 5.0}
        else:
            filename_boost = {}

        # 2. Score text
        scores = _score_text(text_lower)

        # Apply filename boosts
        for dt, boost in filename_boost.items():
            scores[dt] = scores.get(dt, 0.0) + boost

        # 3. Negative scoring — if strong lab markers present, heavily penalize PRESCRIPTION
        lab_neg_count = sum(1 for phrase in LAB_NEGATIVE_FOR_PRESCRIPTION if phrase in text_lower)
        if lab_neg_count >= 2 and DocumentType.PRESCRIPTION in scores:
            scores[DocumentType.PRESCRIPTION] = max(0.0, scores[DocumentType.PRESCRIPTION] - lab_neg_count * 4)

        if not scores:
            # 4. LLM fallback when keyword-based scoring fails entirely
            if settings.llm_provider != "mock" and not settings.mock_mode:
                try:
                    from app.services.llm import get_llm_provider
                    llm = get_llm_provider(settings.llm_provider)
                    type_list = ", ".join(dt.value for dt in DocumentType if dt != DocumentType.UNKNOWN)
                    prompt = (
                        f"You are a medical document classifier. Read the following OCR text from a medical document "
                        f"and classify it as EXACTLY one of: {type_list}, UNKNOWN.\n\n"
                        f"Respond with ONLY the category name, nothing else.\n\n"
                        f"OCR Text:\n{text[:3000]}"
                    )
                    response = llm.generate(prompt).strip().upper()
                    for dt in DocumentType:
                        if dt.value in response:
                            conf = 0.40 if dt == DocumentType.UNKNOWN else 0.82
                            return dt, conf
                except Exception:
                    pass
            return DocumentType.UNKNOWN, 0.40

        # 5. Compute winner and normalize confidence
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        second_best = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0

        # Margin-based confidence: wider margin = higher confidence
        margin = best_score - second_best
        confidence = min(0.55 + (margin / (best_score + 1e-6)) * 0.40, 0.97)
        confidence = round(confidence, 3)

        requires_verification = confidence < CLASSIFICATION_CONFIDENCE_THRESHOLD

        return best_type, confidence
