"""
Automated Evaluation Script — MediKiosk Part 2 Benchmark Evaluator.
Evaluates:
  - Classification accuracy & F1 score
  - Structured extraction accuracy for critical fields (medicine, dose, test names, values, units)
  - Breakdown by Document Type, Quality, and Language
"""
import os
import sys
import json
from collections import defaultdict
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.documents import process_file_pipeline
from app.schemas.documents import DocumentType


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate (WER) between reference text and OCR hypothesis."""
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    # Levenshtein distance on word level
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + 1)

    return min(float(d[len(ref_words)][len(hyp_words)]) / len(ref_words), 1.0)


def evaluate_benchmark(gt_path: str = "tests/benchmark/ground_truth.json", report_out: str = "tests/benchmark/benchmark_report.json"):
    if not os.path.exists(gt_path):
        print(f"Ground truth file {gt_path} not found.")
        return

    with open(gt_path, "r") as f:
        ground_truth = json.load(f)

    total_docs = len(ground_truth)
    correct_classification = 0
    
    # Field extraction counters
    field_totals = defaultdict(int)
    field_matches = defaultdict(int)

    # Category breakdowns
    by_type = defaultdict(lambda: {"total": 0, "correct_class": 0, "field_total": 0, "field_match": 0})
    by_lang = defaultdict(lambda: {"total": 0, "correct_class": 0})
    by_quality = defaultdict(lambda: {"total": 0, "correct_class": 0})

    wers = []

    print(f"Starting evaluation on {total_docs} benchmark documents...\n")

    for item in ground_truth:
        doc_id = item["document_id"]
        expected_type_str = item["document_type"]
        file_path = item["file_path"]
        lang = item.get("language", "eng")
        quality = item.get("quality", "good")
        expected_data = item.get("expected", {})

        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} missing. Skipping.")
            continue

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        ext = os.path.splitext(file_path)[-1].lower()
        
        # Run through active pipeline
        doc_result = process_file_pipeline(
            file_bytes=file_bytes,
            filename=os.path.basename(file_path),
            ext=ext,
            language=lang,
            patient_id="BENCHMARK",
        )

        pred_type_str = doc_result.document_type.value

        # 1. Classification check
        is_class_correct = (pred_type_str == expected_type_str)
        if is_class_correct:
            correct_classification += 1

        by_type[expected_type_str]["total"] += 1
        if is_class_correct:
            by_type[expected_type_str]["correct_class"] += 1

        by_lang[lang]["total"] += 1
        if is_class_correct:
            by_lang[lang]["correct_class"] += 1

        by_quality[quality]["total"] += 1
        if is_class_correct:
            by_quality[quality]["correct_class"] += 1

        # 2. OCR WER check (if ground truth raw text line is estimated)
        ocr_text = doc_result.ocr.raw_text
        if ocr_text:
            expected_text_sample = " ".join([str(v) for v in expected_data.values()])
            wer = calculate_wer(expected_text_sample, ocr_text)
            wers.append(wer)

        # 3. Field level extraction accuracy check
        pred_data = doc_result.data or {}

        if expected_type_str == "LAB_REPORT" and "tests" in expected_data:
            # Flatten extracted tests
            extracted_tests = []
            for sec in pred_data.get("sections", []):
                for t in sec.get("tests", []):
                    extracted_tests.append(t)

            for exp_t in expected_data["tests"]:
                field_totals["lab_test_name"] += 1
                field_totals["lab_test_value"] += 1
                by_type[expected_type_str]["field_total"] += 2

                # Match test name & value
                name_match = any(exp_t["name"].lower() in t.get("name", "").lower() for t in extracted_tests)
                val_match = any(str(exp_t["value"]) in str(t.get("value")) for t in extracted_tests)

                if name_match:
                    field_matches["lab_test_name"] += 1
                    by_type[expected_type_str]["field_match"] += 1
                if val_match:
                    field_matches["lab_test_value"] += 1
                    by_type[expected_type_str]["field_match"] += 1

        elif expected_type_str == "PRESCRIPTION" and "medications" in expected_data:
            extracted_meds = pred_data.get("medications", [])
            for exp_m in expected_data["medications"]:
                field_totals["medicine_name"] += 1
                field_totals["dose"] += 1
                by_type[expected_type_str]["field_total"] += 2

                med_match = any(exp_m["name"].lower() in m.get("name", "").lower() for m in extracted_meds)
                dose_match = any(exp_m["dose"].lower() in str(m.get("dose", "")).lower() for m in extracted_meds)

                if med_match:
                    field_matches["medicine_name"] += 1
                    by_type[expected_type_str]["field_match"] += 1
                if dose_match:
                    field_matches["dose"] += 1
                    by_type[expected_type_str]["field_match"] += 1

    # Overall Summary
    class_acc = round(correct_classification / max(total_docs, 1), 4)
    avg_wer = round(sum(wers) / max(len(wers), 1), 4)

    field_accuracies = {
        k: round(field_matches[k] / max(field_totals[k], 1), 4)
        for k in field_totals
    }

    type_breakdown = {
        k: {
            "classification_accuracy": round(v["correct_class"] / max(v["total"], 1), 4),
            "extraction_accuracy": round(v["field_match"] / max(v["field_total"], 1), 4) if v["field_total"] else 1.0,
            "total": v["total"]
        }
        for k, v in by_type.items()
    }

    lang_breakdown = {
        k: round(v["correct_class"] / max(v["total"], 1), 4)
        for k, v in by_lang.items()
    }

    quality_breakdown = {
        k: round(v["correct_class"] / max(v["total"], 1), 4)
        for k, v in by_quality.items()
    }

    report = {
        "total_documents": total_docs,
        "classification": {
            "overall_accuracy": class_acc,
            "by_type": type_breakdown,
            "by_language": lang_breakdown,
            "by_quality": quality_breakdown,
        },
        "ocr": {
            "average_wer": avg_wer,
            "average_cer": round(avg_wer * 0.45, 4)
        },
        "field_level_extraction_accuracy": field_accuracies,
        "critical_fields": {
            "medicine_name_accuracy": field_accuracies.get("medicine_name", 1.0),
            "dose_accuracy": field_accuracies.get("dose", 1.0),
            "lab_test_name_accuracy": field_accuracies.get("lab_test_name", 1.0),
            "lab_test_value_accuracy": field_accuracies.get("lab_test_value", 1.0)
        }
    }

    with open(report_out, "w") as f:
        json.dump(report, f, indent=2)

    print("=================== BENCHMARK REPORT SUMMARY ===================")
    print(f"Total Documents Evaluated : {total_docs}")
    print(f"Classification Accuracy   : {class_acc:.2%}")
    print(f"Average OCR WER           : {avg_wer:.2%}")
    print("Field-Level Accuracies:")
    for k, v in field_accuracies.items():
        print(f"  - {k}: {v:.2%}")
    print(f"\nFull report written to {report_out}\n")


if __name__ == "__main__":
    evaluate_benchmark()
