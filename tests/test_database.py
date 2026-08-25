import pytest
from app.core.database import get_db, init_db
from app.repositories.consultation_repository import ConsultationRepository
from app.repositories.answer_repository import AnswerRepository
from app.repositories.user_repository import UserRepository
from app.models.user import UserRegister

def test_database_tables_initialization():
    """Verify all 6 required tables exist."""
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r["name"] for r in cursor.fetchall()]
        assert "users" in tables
        assert "consultations" in tables
        assert "questions" in tables
        assert "answers" in tables
        assert "triage_events" in tables
        assert "final_histories" in tables

def test_answer_persistence():
    """Verify answers are saved with input_mode and structured_data."""
    visit_id = ConsultationRepository.create_consultation("USR-000001", "en", "stomach pain")
    ans_id = AnswerRepository.save_answer(
        visit_id=visit_id,
        user_id="USR-000001",
        question_text="Where is the pain?",
        answer_text="Right side",
        input_mode="voice",
        language="en",
        structured_data={"location": "right"}
    )
    assert ans_id.startswith("ANS-")
    records = AnswerRepository.get_by_visit_id(visit_id)
    assert len(records) >= 1
    assert records[0].input_mode == "voice"
    assert records[0].structured_data["location"] == "right"
