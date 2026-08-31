import pytest

def test_rag_patient_isolation(client):
    login_res = client.post("/api/v1/auth/login", json={"username": "doctor1", "password": "doctor123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Patient A
    p_a = client.post("/api/v1/patients", json={"name": "Patient Alpha", "phone": "1111111111"}, headers=headers).json()
    pat_a_id = p_a["patient_id"]

    # Create Patient B
    p_b = client.post("/api/v1/patients", json={"name": "Patient Beta", "phone": "2222222222"}, headers=headers).json()
    pat_b_id = p_b["patient_id"]

    # Add confidential Document to Patient A
    v_a = client.post("/api/v1/visits", json={"patient_id": pat_a_id}, headers=headers).json()
    client.post("/api/v1/documents", json={
        "patient_id": pat_a_id,
        "visit_id": v_a["visit_id"],
        "document_type": "LAB_REPORT",
        "raw_text": "Patient Alpha confidential lab result: Rare Blood Condition Alpha-X Detected.",
        "structured_data": {"condition": "Alpha-X"}
    }, headers=headers)

    # Perform RAG query on Patient B asking for Alpha-X condition
    rag_res_b = client.post(f"/api/v1/patients/{pat_b_id}/query", json={
        "patient_id": pat_b_id,
        "query": "What are the lab results for rare condition Alpha-X?"
    }, headers=headers)

    assert rag_res_b.status_code == 200
    b_data = rag_res_b.json()
    # Confirm Patient B query NEVER returns Patient A's confidential document
    for src in b_data.get("sources", []):
        assert "Alpha" not in src["snippet"]

    # Perform RAG query on Patient A and confirm it retrieves Patient A's data
    rag_res_a = client.post(f"/api/v1/patients/{pat_a_id}/query", json={
        "patient_id": pat_a_id,
        "query": "What are the lab results for rare condition Alpha-X?"
    }, headers=headers)
    assert rag_res_a.status_code == 200
    a_data = rag_res_a.json()
    assert len(a_data.get("sources", [])) > 0
