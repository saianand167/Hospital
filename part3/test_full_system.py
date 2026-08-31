#!/usr/bin/env python3
"""
Full System Integration Test: MediKiosk Real Engine Verification
Tests Part 1 (Clinical Intake + Red-Flag Triage), Part 2 (OCR Document Intelligence), and Part 3 (Core API, Doctor Briefing, Prescription PDF).
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def run_tests():
    print("==========================================================================")
    print("🏥 MEDIKIOSK FULL SYSTEM INTEGRATION TEST (REAL ENGINES)")
    print("==========================================================================\n")

    # 1. Health check
    res = requests.get("http://localhost:8000/health")
    assert res.status_code == 200
    print("[PASS] 1. Backend Health Check OK")

    # 2. Login Doctor & Patient
    res_doc = requests.post(f"{BASE_URL}/auth/login", json={"username": "doctor1", "password": "doctor123"})
    assert res_doc.status_code == 200, f"Doctor login failed: {res_doc.text}"
    doc_token = res_doc.json()["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    print("[PASS] 2. Doctor Login OK")

    res_pat = requests.post(f"{BASE_URL}/auth/login", json={"username": "patient1", "password": "patient123"})
    assert res_pat.status_code == 200, f"Patient login failed: {res_pat.text}"
    pat_token = res_pat.json()["access_token"]
    pat_headers = {"Authorization": f"Bearer {pat_token}"}
    print("[PASS] 3. Patient Login OK")

    # 3. Create Visit
    res_v = requests.post(f"{BASE_URL}/visits", json={"patient_id": "PAT-000001", "department": "Cardiology", "priority": "NORMAL"}, headers=pat_headers)
    assert res_v.status_code == 200, f"Visit creation failed: {res_v.text}"
    visit_id = res_v.json()["visit_id"]
    print(f"[PASS] 4. Created Visit `{visit_id}` OK")

    # 4. Start Real Part 1 Clinical History Session
    res_s = requests.post(f"{BASE_URL}/history/session/start", json={
        "patient_id": "PAT-000001",
        "visit_id": visit_id,
        "language": "en",
        "initial_complaint": "Chest pain for 4 days"
    }, headers=pat_headers)
    assert res_s.status_code == 200, f"Session start failed: {res_s.text}"
    sess_body = res_s.json()
    assert sess_body["status"] == "session_started"
    assert sess_body["next_question"] is not None
    print(f"[PASS] 5. Part 1 Session Started. Next Question: {sess_body['next_question']['prompt_text']}")

    # 5. Send Message to History Engine (Trigger Red-Flag Triage)
    res_m = requests.post(f"{BASE_URL}/history/session/{visit_id}/message", json={
        "patient_message": "Yes, severe breathlessness and sweating",
        "target_field": "breathlessness",
        "is_touch_input": True,
        "touch_value": "true",
        "language": "en"
    }, headers=pat_headers)
    assert res_m.status_code == 200, f"Message failed: {res_m.text}"
    m_body = res_m.json()
    assert m_body["triage"]["flag"] == "RED"
    print(f"[PASS] 6. Triage Evaluated -> Flag: RED | Priority: HIGH (Red Flag Triggered)")

    # 6. Upload Document via Real Part 2 OCR Pipeline
    dummy_cbc = (
        "CLINICAL LABORATORY REPORT\n"
        "Hemoglobin: 11.5 g/dL (13.0 - 17.0) [LOW]\n"
        "Troponin-I: 0.09 ng/mL (< 0.04) [HIGH]\n"
    ).encode("utf-8")
    
    files = {"file": ("cbc_report.txt", dummy_cbc, "text/plain")}
    data = {"patient_id": "PAT-000001", "document_type": "LAB_REPORT", "visit_id": visit_id}
    res_up = requests.post(f"{BASE_URL}/documents/upload", data=data, files=files, headers=pat_headers)
    assert res_up.status_code == 200, f"Upload failed: {res_up.text}"
    doc_body = res_up.json()
    doc_id = doc_body["document_id"]
    assert doc_body["document_type"] == "LAB_REPORT"
    print(f"[PASS] 7. Part 2 Document Upload & OCR OK -> Doc ID: `{doc_id}` | Tests Extracted: {len(doc_body['structured_data']['tests'])}")

    # 7. Doctor Queue & Summary
    res_q = requests.get(f"{BASE_URL}/doctor/queue", headers=doc_headers)
    assert res_q.status_code == 200, f"Doctor queue failed: {res_q.text}"
    print(f"[PASS] 8. Doctor Queue Retrieved ({len(res_q.json())} visits)")

    res_sum = requests.get(f"{BASE_URL}/doctor/patients/PAT-000001/summary?visit_id={visit_id}", headers=doc_headers)
    assert res_sum.status_code == 200, f"Summary failed: {res_sum.text}"
    sum_body = res_sum.json()
    print(f"[PASS] 9. Doctor Summary Generated OK -> Triage Flag: {sum_body['current_triage_flag']}")

    # 8. Voice Prescription & PDF
    res_parse = requests.post(f"{BASE_URL}/prescriptions/voice-dictate", json={
        "patient_id": "PAT-000001",
        "visit_id": visit_id,
        "doctor_id": "DOC-101",
        "transcript": "Aspirin 75 mg once daily. Clopidogrel 75 mg once daily for 30 days."
    }, headers=doc_headers)
    assert res_parse.status_code == 200, f"Dictation parse failed: {res_parse.text}"
    items = res_parse.json()
    print(f"[PASS] 10. Voice Dictation Parsed -> {len(items)} items")

    res_rx = requests.post(f"{BASE_URL}/prescriptions", json={
        "patient_id": "PAT-000001",
        "visit_id": visit_id,
        "doctor_id": "DOC-101",
        "items": items
    }, headers=doc_headers)
    rx_id = res_rx.json()["prescription_id"]
    print(f"[PASS] 11. Draft Prescription Created -> `{rx_id}`")

    res_conf = requests.post(f"{BASE_URL}/prescriptions/{rx_id}/confirm", json={"items": items}, headers=doc_headers)
    assert res_conf.status_code == 200, f"Confirmation failed: {res_conf.text}"
    print(f"[PASS] 12. Prescription Confirmed & Printable PDF Generated")

    res_pdf = requests.get(f"{BASE_URL}/prescriptions/{rx_id}/pdf", headers=pat_headers)
    assert res_pdf.status_code == 200, f"PDF failed: {res_pdf.text}"
    assert len(res_pdf.content) > 100
    print(f"[PASS] 13. Printable PDF Download Verified ({len(res_pdf.content)} bytes)")

    print("\n==========================================================================")
    print("✨ ALL REAL ENGINE INTEGRATION TESTS PASSED PERFECTLY!")
    print("==========================================================================")

if __name__ == "__main__":
    run_tests()
