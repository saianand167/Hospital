import pytest
from app.clinical.question_engine import ClinicalQuestionEngine
from app.models.history import ClinicalHistoryJSON, ChiefComplaint, HPIState

def test_initial_question_must_be_general_not_chest_pain():
    """Initial question must be 'What are you suffering from?', NOT hardcoded to chest pain."""
    history = ClinicalHistoryJSON(
        patient_id="USR-000001",
        visit_id="VIS-000001",
        language="en",
        chief_complaint=ChiefComplaint(text=None)
    )
    prompt, is_completed = ClinicalQuestionEngine.get_next_question(history)
    assert not is_completed
    assert prompt is not None
    assert prompt.field_name == "chief_complaint"
    assert "What are you suffering from" in prompt.prompt_text

def test_dynamic_question_selection_for_abdominal_pain():
    """When complaint is stomach/abdominal pain, questionnaire dynamically loads abdominal_pain.yaml."""
    history = ClinicalHistoryJSON(
        patient_id="USR-000001",
        visit_id="VIS-000001",
        language="en",
        chief_complaint=ChiefComplaint(text="stomach pain", canonical="abdominal_pain"),
        hpi=HPIState(duration_days=2.0)
    )
    prompt, is_completed = ClinicalQuestionEngine.get_next_question(history)
    assert not is_completed
    assert prompt is not None
    assert prompt.field_name == "location"
    assert any(opt["value"] == "right lower" for opt in prompt.options)

def test_question_engine_telugu_general_localization():
    """Test Telugu localization for initial general question."""
    history = ClinicalHistoryJSON(
        patient_id="USR-000001",
        visit_id="VIS-000001",
        language="te",
        chief_complaint=ChiefComplaint(text=None)
    )
    prompt, is_completed = ClinicalQuestionEngine.get_next_question(history)
    assert not is_completed
    assert prompt is not None
    assert "ఆరోగ్య సమస్య" in prompt.prompt_text
