import pytest
import asyncio
from app.llm.extraction import ClinicalExtractor
from app.models.history import ClinicalHistoryJSON, ChiefComplaint, HPIState

@pytest.mark.asyncio
async def test_extract_english_complaint_and_duration():
    """Test standard English intake extraction."""
    history = ClinicalHistoryJSON(patient_id="P1", visit_id="V1", language="en")
    text = "I have had chest pain on the left side for four days."
    res = await ClinicalExtractor.extract_and_update(text, history)
    
    assert res.chief_complaint.text == "chest pain"
    assert res.hpi.duration_days == 4.0
    assert res.hpi.location == "left"
    # Unknown fields must remain None!
    assert res.hpi.radiation is None
    assert res.hpi.breathlessness is None

@pytest.mark.asyncio
async def test_extract_telugu_response():
    """Test pure Telugu intake extraction."""
    history = ClinicalHistoryJSON(patient_id="P1", visit_id="V1", language="te")
    text = "నాకు నాలుగు రోజులుగా ఎడమ వైపు ఛాతి నొప్పి ఉంది"
    res = await ClinicalExtractor.extract_and_update(text, history)
    
    assert res.chief_complaint.text == "chest pain"
    assert res.hpi.duration_days == 4.0
    assert res.hpi.location == "left"

@pytest.mark.asyncio
async def test_extract_mixed_code_switching():
    """Test mixed Telugu-English code switching."""
    history = ClinicalHistoryJSON(patient_id="P1", visit_id="V1", language="te")
    text = "నాకు four days నుంచి chest pain ఉంది, left side."
    res = await ClinicalExtractor.extract_and_update(text, history)
    
    assert res.chief_complaint.text == "chest pain"
    assert res.hpi.duration_days == 4.0
    assert res.hpi.location == "left"

@pytest.mark.asyncio
async def test_extract_hindi_response():
    """Test Hindi intake extraction."""
    history = ClinicalHistoryJSON(patient_id="P1", visit_id="V1", language="hi")
    text = "मुझे चार दिनों से सीने में बाईं तरफ दर्द है"
    res = await ClinicalExtractor.extract_and_update(text, history)
    
    assert res.chief_complaint.text == "chest pain"
    assert res.hpi.duration_days == 4.0
    assert res.hpi.location == "left"

@pytest.mark.asyncio
async def test_negation_fever_and_breathlessness():
    """Test critical negation distinction: 'I don't have fever' vs 'I have fever'."""
    history = ClinicalHistoryJSON(patient_id="P1", visit_id="V1", language="en")
    
    # 1. Negative statement
    neg_text = "I don't have fever and no breathlessness."
    res = await ClinicalExtractor.extract_and_update(neg_text, history)
    assert res.hpi.fever is False
    assert res.hpi.breathlessness is False

    # 2. Positive statement
    pos_history = ClinicalHistoryJSON(patient_id="P2", visit_id="V2", language="en")
    pos_text = "I have fever."
    res_pos = await ClinicalExtractor.extract_and_update(pos_text, pos_history)
    assert res_pos.hpi.fever is True
    assert res_pos.hpi.breathlessness is None  # Unmentioned remains None!
