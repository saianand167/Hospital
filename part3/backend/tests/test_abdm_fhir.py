import pytest

def test_abdm_and_fhir_endpoints(client):
    login_res = client.post("/api/v1/auth/login", json={"username": "doctor1", "password": "doctor123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ABDM Record creation
    abdm_res = client.post("/api/v1/interop/abdm/create-record/PAT-000001", headers=headers)
    assert abdm_res.status_code == 200
    assert "abdm_record_id" in abdm_res.json()
    assert abdm_res.json()["status"] == "LINKED"

    # FHIR Patient Export
    fhir_pat_res = client.get("/api/v1/interop/fhir/patient/PAT-000001", headers=headers)
    assert fhir_pat_res.status_code == 200
    assert fhir_pat_res.json()["resourceType"] == "Patient"
    assert fhir_pat_res.json()["id"] == "PAT-000001"
