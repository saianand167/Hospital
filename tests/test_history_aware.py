import pytest
import asyncio
from app.clinical.history_aware_retriever import HistoryAwareRetriever
from app.services.history_service import HistoryService
from app.repositories.consultation_repository import ConsultationRepository
from app.repositories.answer_repository import AnswerRepository

def test_generate_top_10_retrieval_queries():
    """Verify Step 2 generates the top 10 historical retrieval queries."""
    queries = HistoryAwareRetriever.generate_retrieval_queries(
        current_input="it started yesterday",
        active_complaint="abdominal pain"
    )
    assert len(queries) == 10
    assert any("chief complaint" in q.lower() for q in queries)
    assert any("duration" in q.lower() for q in queries)
    assert any("red-flag" in q.lower() for q in queries)
    assert any("allergies" in q.lower() for q in queries)
    assert any("contradict" in q.lower() for q in queries)

def test_history_aware_context_retrieval_and_recency():
    """Verify Steps 3, 4, 5 retrieve recent turns and prior visit context with recency weighting."""
    user_id = "USR-000001"
    visit_id = ConsultationRepository.create_consultation(user_id=user_id, language="en", complaint="diarrhea")
    
    # Simulate earlier dialogue turns
    AnswerRepository.save_answer(
        visit_id=visit_id,
        user_id=user_id,
        question_text="What are you suffering from today?",
        answer_text="i am having loose motions",
        input_mode="text",
        language="en",
        structured_data={"chief_complaint": "diarrhea"}
    )
    AnswerRepository.save_answer(
        visit_id=visit_id,
        user_id=user_id,
        question_text="How many days have you been having loose motions?",
        answer_text="for 2 days",
        input_mode="voice",
        language="en",
        structured_data={"duration_days": 2.0}
    )

    # Run retriever for turn 3
    context = HistoryAwareRetriever.retrieve_historical_context(
        user_id=user_id,
        visit_id=visit_id,
        current_input="3 to 4 times per day"
    )

    assert context["user_id"] == user_id
    assert context["visit_id"] == visit_id
    assert len(context["recent_conversation_turns"]) == 2
    assert "CURRENT SESSION DIALOGUE HISTORY" in context["context_summary_for_llm"]
    assert "loose motions" in context["context_summary_for_llm"]
    assert len(context["retrieval_queries_used"]) == 10
