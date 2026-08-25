import pytest
import asyncio
from app.services.history_service import HistoryService
from app.services.consultation_service import ConsultationService

def test_multiple_users_and_visits_isolation():
    """Verify Patient A (USR-000001, VIS-000001) and Patient B (USR-000002, VIS-000002) states never cross-contaminate."""
    # Patient A Consultation
    h_a, _ = HistoryService.start_session(user_id="USR-000001", language="en")
    vis_a = h_a.visit_id
    asyncio.run(HistoryService.process_message(
        visit_id=vis_a,
        patient_message="I have stomach pain for two days on the right side"
    ))

    # Patient B Consultation
    h_b, _ = HistoryService.start_session(user_id="USR-000002", language="te")
    vis_b = h_b.visit_id
    asyncio.run(HistoryService.process_message(
        visit_id=vis_b,
        patient_message="నాకు మూడు రోజులుగా జ్వరం ఉంది"
    ))

    # Verify Patient A State
    state_a = HistoryService.get_session(vis_a)
    assert state_a.patient_id == "USR-000001"
    assert "stomach" in state_a.chief_complaint.text.lower() or "abdominal" in state_a.chief_complaint.text.lower()
    assert state_a.hpi.duration_days == 2.0
    assert state_a.hpi.location == "right"

    # Verify Patient B State
    state_b = HistoryService.get_session(vis_b)
    assert state_b.patient_id == "USR-000002"
    assert "fever" in state_b.chief_complaint.text.lower() or "జ్వరం" in state_b.chief_complaint.text.lower()
    assert state_b.hpi.duration_days == 3.0
    assert state_b.hpi.location is None
