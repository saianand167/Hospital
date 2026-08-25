import pytest
from app.clinical.triage_rules import RedFlagRuleEngine
from app.models.history import HPIState

def test_red_flag_chest_pain_with_breathlessness():
    """Rule 1: Chest pain with breathlessness must trigger RED priority."""
    hpi = HPIState(breathlessness=True, severity=5)
    triage = RedFlagRuleEngine.evaluate("chest pain", hpi)
    assert triage.flag == "RED"
    assert triage.priority is True
    assert "CHEST_PAIN_WITH_BREATHLESSNESS" in triage.reason_codes

def test_red_flag_chest_pain_with_sweating_and_radiation():
    """Rule 2: Severe chest pain (>=7) with sweating or radiation to arm must trigger RED."""
    hpi = HPIState(severity=8, radiation="left arm", sweating=True)
    triage = RedFlagRuleEngine.evaluate("chest pain", hpi)
    assert triage.flag == "RED"
    assert triage.priority is True
    assert "SEVERE_CHEST_PAIN_WITH_AUTONOMIC_FEATURES" in triage.reason_codes

def test_red_flag_fever_with_respiratory_distress():
    """Rule 4: Fever with breathing difficulty must trigger RED."""
    hpi = HPIState(fever=True, breathlessness=True)
    triage = RedFlagRuleEngine.evaluate("fever", hpi)
    assert triage.flag == "RED"
    assert triage.priority is True
    assert "FEVER_WITH_RESPIRATORY_DISTRESS" in triage.reason_codes

def test_yellow_flag_severe_pain_alone():
    """Rule 5: Isolated severe pain (>=8) without autonomic red flags triggers YELLOW."""
    hpi = HPIState(severity=9, breathlessness=False, sweating=False, dizziness=False)
    triage = RedFlagRuleEngine.evaluate("headache", hpi)
    assert triage.flag == "YELLOW"
    assert triage.priority is False

def test_green_flag_routine_condition():
    """Routine mild symptoms with no red flags must produce GREEN routine flag."""
    hpi = HPIState(severity=3, duration_days=2, breathlessness=False, sweating=False)
    triage = RedFlagRuleEngine.evaluate("chest pain", hpi)
    assert triage.flag == "GREEN"
    assert triage.priority is False
    assert len(triage.reason_codes) == 0
