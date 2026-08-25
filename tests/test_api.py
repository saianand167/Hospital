import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_auth_register_and_login_flow():
    uid = uuid.uuid4().hex[:6]
    # Register
    reg_data = {
        "full_name": "API Test User",
        "username": f"api_user_{uid}",
        "email": f"api_{uid}@hospital.org",
        "password": "apipassword123",
        "phone": "9988776655",
        "preferred_language": "te"
    }
    r_reg = client.post("/auth/register", json=reg_data)
    assert r_reg.status_code == 201
    user_data = r_reg.json()
    assert user_data["user_id"].startswith("USR-")
    assert user_data["username"] == f"api_user_{uid}"

    # Login
    login_data = {
        "username_or_email": f"api_user_{uid}",
        "password": "apipassword123"
    }
    r_login = client.post("/auth/login", json=login_data)
    assert r_login.status_code == 200
    assert r_login.json()["user_id"] == user_data["user_id"]

def test_session_lifecycle_and_history():
    # Start Session
    start_payload = {
        "user_id": "USR-000001",
        "language": "en"
    }
    r_start = client.post("/session/start", json=start_payload)
    assert r_start.status_code == 200
    data = r_start.json()
    visit_id = data["history"]["visit_id"]
    assert visit_id.startswith("VIS-")
    # First question must be general
    assert data["next_question"]["field_name"] == "chief_complaint"

    # Send first complaint answer
    msg_payload = {
        "message": "I have stomach pain from yesterday on the right side",
        "target_field": "chief_complaint",
        "question_text": "What are you suffering from today?"
    }
    r_msg = client.post(f"/session/{visit_id}/message", json=msg_payload)
    assert r_msg.status_code == 200
    msg_data = r_msg.json()
    assert "stomach" in msg_data["history"]["chief_complaint"]["text"].lower() or "abdominal" in msg_data["history"]["chief_complaint"]["text"].lower()

    # Check conversation history endpoint
    r_hist = client.get(f"/session/{visit_id}/history")
    assert r_hist.status_code == 200
    answers = r_hist.json()
    assert len(answers) >= 1
    assert answers[0]["visit_id"] == visit_id
