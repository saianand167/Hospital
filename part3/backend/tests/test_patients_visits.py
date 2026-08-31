import pytest

def test_patient_and_repeat_visit_flow(client):
    # 1. Login as doctor
    login_res = client.post("/api/v1/auth/login", json={"username": "doctor1", "password": "doctor123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create new patient
    pat_res = client.post("/api/v1/patients", json={
        "name": "Anil Sharma",
        "date_of_birth": "1990-01-01",
        "gender": "Male",
        "phone": "9988776655",
        "preferred_language": "English"
    }, headers=headers)
    assert pat_res.status_code == 200
    patient_id = pat_res.json()["patient_id"]
    assert patient_id.startswith("PAT-")

    # 3. First visit (Visit 1: Chest pain)
    v1_res = client.post("/api/v1/visits", json={
        "patient_id": patient_id,
        "department": "Cardiology",
        "priority": "HIGH"
    }, headers=headers)
    assert v1_res.status_code == 200
    visit_id_1 = v1_res.json()["visit_id"]

    # Store Part 1 clinical history for Visit 1
    h1_res = client.post(f"/api/v1/history/mock-generate/{visit_id_1}?chief_complaint=Chest%20pain&is_red_flag=true", headers=headers)
    assert h1_res.status_code == 200

    # Complete Visit 1
    client.post(f"/api/v1/visits/{visit_id_1}/complete", headers=headers)

    # 4. Repeat visit (Visit 2: Follow up / Fever)
    v2_res = client.post("/api/v1/visits", json={
        "patient_id": patient_id,
        "department": "General Medicine",
        "priority": "NORMAL"
    }, headers=headers)
    assert v2_res.status_code == 200
    visit_id_2 = v2_res.json()["visit_id"]
    assert visit_id_1 != visit_id_2

    # Store Part 1 clinical history for Visit 2
    h2_res = client.post(f"/api/v1/history/mock-generate/{visit_id_2}?chief_complaint=Fever&is_red_flag=false", headers=headers)
    assert h2_res.status_code == 200

    # 5. Verify Visit History preserves Visit 1 & Visit 2 without overwriting
    visits_res = client.get(f"/api/v1/patients/{patient_id}/visits", headers=headers)
    assert visits_res.status_code == 200
    visits_list = visits_res.json()
    assert len(visits_list) == 2
    v_ids = [v["visit_id"] for v in visits_list]
    assert visit_id_1 in v_ids
    assert visit_id_2 in v_ids
