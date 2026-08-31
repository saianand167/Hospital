import pytest

def test_prescription_voice_and_confirmation_flow(client):
    login_res = client.post("/api/v1/auth/login", json={"username": "doctor1", "password": "doctor123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Voice dictation to structured draft
    dict_res = client.post("/api/v1/prescriptions/voice-dictate", json={
        "patient_id": "PAT-000001",
        "visit_id": "VIS-000001",
        "doctor_id": "DOC-101",
        "transcript": "Paracetamol 500 mg twice daily for three days after food."
    }, headers=headers)
    assert dict_res.status_code == 200
    draft_items = dict_res.json()
    assert len(draft_items) >= 1
    assert "Paracetamol" in draft_items[0]["medicine_name"]

    # Create draft prescription
    rx_create_res = client.post("/api/v1/prescriptions", json={
        "patient_id": "PAT-000001",
        "visit_id": "VIS-000001",
        "doctor_id": "DOC-101",
        "items": draft_items
    }, headers=headers)
    assert rx_create_res.status_code == 200
    rx_id = rx_create_res.json()["prescription_id"]
    assert rx_create_res.json()["status"] == "DRAFT"

    # Confirm prescription & generate PDF
    confirm_res = client.post(f"/api/v1/prescriptions/{rx_id}/confirm", json={"items": draft_items}, headers=headers)
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "FINAL"

    # Download PDF
    pdf_res = client.get(f"/api/v1/prescriptions/{rx_id}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
