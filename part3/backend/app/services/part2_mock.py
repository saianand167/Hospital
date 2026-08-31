from typing import Dict, Any
import datetime

class Part2DocumentEngineMock:
    @staticmethod
    def process_document(
        patient_id: str,
        visit_id: str,
        document_type: str,
        file_name: str = "report.pdf"
    ) -> Dict[str, Any]:
        """
        Simulate Part 2 Medical Document Engine output structure.
        """
        doc_id = f"DOC-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        if document_type.upper() == "LAB_REPORT":
            return {
                "document_id": doc_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "document_type": "LAB_REPORT",
                "document_date": datetime.datetime.utcnow().isoformat(),
                "raw_text": "COMPLETE BLOOD COUNT (CBC)\nHemoglobin: 13.5 g/dL (Normal 13-17)\nWBC Count: 8,500 /mcL (Normal 4000-11000)\nPlatelets: 250,000 /mcL (Normal 150000-450000)\nTroponin-I: 0.04 ng/mL (Normal < 0.04)",
                "data": {
                    "tests": [
                        {"name": "Hemoglobin", "value": "13.5", "unit": "g/dL", "flag": "NORMAL"},
                        {"name": "WBC Count", "value": "8500", "unit": "/mcL", "flag": "NORMAL"},
                        {"name": "Platelets", "value": "250000", "unit": "/mcL", "flag": "NORMAL"},
                        {"name": "Troponin-I", "value": "0.04", "unit": "ng/mL", "flag": "BORDERLINE"}
                    ]
                },
                "confidence": {
                    "ocr": 0.98,
                    "extraction": 0.95
                },
                "verification_required": False,
                "verified": True
            }
        elif document_type.upper() == "XRAY":
            return {
                "document_id": doc_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "document_type": "XRAY",
                "document_date": datetime.datetime.utcnow().isoformat(),
                "raw_text": "CHEST RADIOGRAPH (PA VIEW)\nFindings: Clear lung fields bilaterally. Cardiac silhouette normal in size and contour. No pleural effusion or pneumothorax.\nImpression: Normal chest radiograph.",
                "data": {
                    "findings": "Clear lung fields bilaterally. Normal cardiac size.",
                    "impression": "Normal chest radiograph."
                },
                "confidence": {
                    "ocr": 0.95,
                    "extraction": 0.92
                },
                "verification_required": False,
                "verified": True
            }
        elif document_type.upper() == "HANDWRITTEN_PRESCRIPTION":
            return {
                "document_id": doc_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "document_type": "HANDWRITTEN_PRESCRIPTION",
                "document_date": datetime.datetime.utcnow().isoformat(),
                "raw_text": "Rx (Handwritten OCR output - unverified):\n1. Paracetamol 500mg - 1-0-1 - 3 days\n2. Amoxicillin 500mg - 1-1-1 - 5 days (Unclear handwriting)",
                "data": {
                    "medications": [
                        {"medicine_name": "Paracetamol", "dose": "500 mg", "frequency": "BD (1-0-1)", "duration": "3 days"},
                        {"medicine_name": "Amoxicillin (Needs check)", "dose": "500 mg", "frequency": "TDS (1-1-1)", "duration": "5 days"}
                    ]
                },
                "confidence": {
                    "ocr": 0.65,
                    "extraction": 0.60
                },
                "verification_required": True,
                "verified": False  # Handled by Pharmacist Verification
            }
        else:
            return {
                "document_id": doc_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "document_type": document_type.upper(),
                "document_date": datetime.datetime.utcnow().isoformat(),
                "raw_text": f"General medical document of type {document_type}",
                "data": {"summary": "Standard clinical record document"},
                "confidence": {"ocr": 0.90, "extraction": 0.90},
                "verification_required": False,
                "verified": True
            }
