from typing import Dict, Any, List
from datetime import datetime
from app.models.triage import TriageResult
from app.models.history import HPIState

class RedFlagRuleEngine:
    """
    Deterministic clinical red-flag & triage safety engine.
    NEVER produces medical diagnoses; performs triage-assistance classification only.
    """
    
    @staticmethod
    def evaluate(
        chief_complaint: str,
        hpi: HPIState,
        past_history: List[str] = None
    ) -> TriageResult:
        complaint_lower = (chief_complaint or "").lower()
        reasons: List[str] = []
        triggering: Dict[str, Any] = {}
        
        # Rule 1: Chest Pain with Acute Breathlessness (RED)
        if ("chest" in complaint_lower or "cardiac" in complaint_lower or "గుండె" in complaint_lower or "छाती" in complaint_lower):
            if hpi.breathlessness is True:
                reasons.append("CHEST_PAIN_WITH_BREATHLESSNESS")
                triggering["chief_complaint"] = chief_complaint
                triggering["breathlessness"] = True
                
            # Rule 2: Chest Pain + High Severity (>=7) + Radiation to Arm/Jaw + Sweating (RED)
            if (hpi.severity is not None and hpi.severity >= 7) and (hpi.sweating is True or (hpi.radiation and "arm" in str(hpi.radiation).lower())):
                reasons.append("SEVERE_CHEST_PAIN_WITH_AUTONOMIC_FEATURES")
                triggering["severity"] = hpi.severity
                triggering["sweating"] = hpi.sweating
                triggering["radiation"] = hpi.radiation
                
            # Rule 3: Chest Pain + Syncope / Dizziness (RED)
            if hpi.dizziness is True:
                reasons.append("CHEST_PAIN_WITH_SYNCOPE_DIZZINESS")
                triggering["dizziness"] = True

        # Rule 4: High Fever with Breathing Distress (RED)
        if "fever" in complaint_lower or "జ్వరం" in complaint_lower or "बुखार" in complaint_lower:
            if hpi.breathlessness is True:
                reasons.append("FEVER_WITH_RESPIRATORY_DISTRESS")
                triggering["fever"] = True
                triggering["breathlessness"] = True

        # Rule 5: Severe Intensity (Severity >= 8) alone (YELLOW)
        if hpi.severity is not None and hpi.severity >= 8 and not reasons:
            return TriageResult(
                flag="YELLOW",
                priority=False,
                reason_codes=["SEVERE_PAIN_REQUIRING_PROMPT_EVALUATION"],
                triggering_parameters={"severity": hpi.severity},
                evaluated_at=datetime.now().isoformat(),
                recommendation="Priority queuing recommended for prompt clinical assessment."
            )

        # RED Evaluation
        if reasons:
            return TriageResult(
                flag="RED",
                priority=True,
                reason_codes=reasons,
                triggering_parameters=triggering,
                evaluated_at=datetime.now().isoformat(),
                recommendation="Priority clinical attention required. Alert triage nursing staff immediately."
            )

        # GREEN Evaluation (Routine)
        return TriageResult(
            flag="GREEN",
            priority=False,
            reason_codes=[],
            triggering_parameters={},
            evaluated_at=datetime.now().isoformat(),
            recommendation="Proceed with standard clinical consultation workflow."
        )
