import datetime
from typing import Dict, Any, List
import uuid

class ABDMService:
    """Abstract ABDM Interface for Ayushman Bharat Digital Mission Interoperability"""
    def create_record(self, patient_id: str, record_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def share_record(self, abha_id: str, record_id: str, consent_id: str) -> bool:
        raise NotImplementedError

    def fetch_record(self, record_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class MockABDMService(ABDMService):
    """Mock ABDM Adapter for SIH Prototype Demonstration"""
    def __init__(self):
        self._records = {}

    def create_record(self, patient_id: str, record_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        abdm_record_id = f"ABDM-REC-{uuid.uuid4().hex[:8].upper()}"
        record = {
            "abdm_record_id": abdm_record_id,
            "patient_id": patient_id,
            "abha_id": f"{patient_id.lower()}@abdm",
            "record_type": record_type,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "status": "LINKED",
            "data": data
        }
        self._records[abdm_record_id] = record
        return record

    def share_record(self, abha_id: str, record_id: str, consent_id: str) -> bool:
        if record_id in self._records:
            self._records[record_id]["status"] = f"SHARED_CONSENT_{consent_id}"
            return True
        return False

    def fetch_record(self, record_id: str) -> Dict[str, Any]:
        return self._records.get(record_id, {"error": "ABDM Record not found"})


# --- FHIR Converters (FHIR R4 JSON standard structures) ---

def patient_to_fhir(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert patient entity to FHIR R4 Patient Resource"""
    return {
        "resourceType": "Patient",
        "id": patient_data.get("patient_id"),
        "identifier": [
            {
                "system": "https://healthid.ndhm.gov.in",
                "value": patient_data.get("patient_id")
            }
        ],
        "name": [
            {
                "use": "official",
                "text": patient_data.get("name")
            }
        ],
        "gender": patient_data.get("gender", "unknown").lower(),
        "birthDate": patient_data.get("date_of_birth"),
        "telecom": [
            {
                "system": "phone",
                "value": patient_data.get("phone")
            }
        ] if patient_data.get("phone") else []
    }

def clinical_history_to_fhir(history_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Part 1 clinical history to FHIR R4 Condition / Encounter Resource"""
    patient_id = history_data.get("patient_id", "PAT-UNKNOWN")
    visit_id = history_data.get("visit_id", "VIS-UNKNOWN")
    cc = history_data.get("chief_complaint", {})
    complaint_text = cc.get("complaint", "Clinical Consultation") if isinstance(cc, dict) else str(cc)

    return {
        "resourceType": "Encounter",
        "id": f"fhir-encounter-{visit_id}",
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory"
        },
        "subject": {
            "reference": f"Patient/{patient_id}"
        },
        "reasonCode": [
            {
                "text": complaint_text
            }
        ],
        "contained": [
            {
                "resourceType": "Observation",
                "id": f"obs-{visit_id}",
                "status": "final",
                "code": {"text": "Chief Complaint & History"},
                "valueString": str(history_data)
            }
        ]
    }

def lab_report_to_fhir(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Part 2 lab document to FHIR R4 DiagnosticReport Resource"""
    patient_id = doc_data.get("patient_id", "PAT-UNKNOWN")
    doc_id = doc_data.get("document_id", "DOC-UNKNOWN")
    structured = doc_data.get("structured_data", {}) or {}

    observations = []
    if "tests" in structured and isinstance(structured["tests"], list):
        for idx, test in enumerate(structured["tests"]):
            observations.append({
                "resourceType": "Observation",
                "id": f"obs-{doc_id}-{idx}",
                "status": "final",
                "code": {"text": test.get("name", "Lab Test")},
                "valueQuantity": {
                    "value": float(test.get("value", 0)) if str(test.get("value", "")).replace(".","").isdigit() else 0,
                    "unit": test.get("unit", "")
                },
                "interpretation": [{"text": test.get("flag", "NORMAL")}]
            })

    return {
        "resourceType": "DiagnosticReport",
        "id": f"fhir-doc-{doc_id}",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "LAB",
                        "display": "Laboratory"
                    }
                ]
            }
        ],
        "subject": {"reference": f"Patient/{patient_id}"},
        "issued": doc_data.get("document_date", datetime.datetime.utcnow().isoformat()),
        "conclusion": doc_data.get("raw_text", ""),
        "contained": observations
    }

def prescription_to_fhir(rx_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert prescription entity to FHIR R4 MedicationRequest Bundle"""
    patient_id = rx_data.get("patient_id", "PAT-UNKNOWN")
    rx_id = rx_data.get("prescription_id", "RX-UNKNOWN")
    items = rx_data.get("items", [])

    requests = []
    for idx, item in enumerate(items):
        requests.append({
            "resourceType": "MedicationRequest",
            "id": f"medreq-{rx_id}-{idx}",
            "status": "active" if rx_data.get("status") == "FINAL" else "draft",
            "intent": "order",
            "medicationCodeableConcept": {
                "text": item.get("medicine_name")
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "dosageInstruction": [
                {
                    "text": f"{item.get('dose')} {item.get('frequency')} for {item.get('duration')}. {item.get('instructions')}",
                    "route": {"text": item.get("route", "Oral")}
                }
            ]
        })

    return {
        "resourceType": "Bundle",
        "id": f"fhir-rx-bundle-{rx_id}",
        "type": "collection",
        "entry": [{"resource": req} for req in requests]
    }

mock_abdm_service = MockABDMService()
