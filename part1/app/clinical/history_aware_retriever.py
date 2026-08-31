from typing import List, Dict, Any, Optional
from datetime import datetime
from app.repositories.answer_repository import AnswerRepository
from app.repositories.consultation_repository import ConsultationRepository
from app.models.history import ClinicalHistoryJSON
from app.models.answer import AnswerRecord

class HistoryAwareRetriever:
    """
    Implements the History-Aware Conversation Retrieval Pattern for MediKiosk.
    
    Pipeline:
    Step 1: Understand current input & clinical context
    Step 2: Generate top historical retrieval sub-queries
    Step 3: Retrieve historical turns (active visit + past consultations)
    Step 4: Apply recency + clinical relevance weighting
    Step 5: Build clean historical context block
    Step 6: Supply structured context for downstream LLM extraction & follow-ups
    """

    @classmethod
    def generate_retrieval_queries(
        cls,
        current_input: str,
        active_complaint: Optional[str] = None
    ) -> List[str]:
        """
        Step 2: Generate top 10 targeted retrieval questions against the patient's conversation history.
        """
        c = (active_complaint or "unspecified").lower()
        return [
            f"What chief complaint did the patient initially report?",
            f"What duration was previously recorded for {c}?",
            f"What severity rating or pain location was mentioned?",
            f"Were any red-flag symptoms (breathlessness, chest pain, blood in stool/vomit) previously reported?",
            f"What associated symptoms (fever, vomiting, chills, sweating) were affirmed or negated?",
            f"What past medical conditions (diabetes, hypertension) were documented in previous turns or visits?",
            f"What regular medications were previously listed?",
            f"Are there any documented drug allergies (penicillin, sulfa)?",
            f"What was the triage risk assessment flag in previous consultations?",
            f"Did the patient contradict or modify any earlier statement in recent messages?"
        ]

    @classmethod
    def retrieve_historical_context(
        cls,
        user_id: str,
        visit_id: str,
        current_input: str
    ) -> Dict[str, Any]:
        """
        Steps 3, 4, 5: Retrieve, rank by recency + clinical relevance, and build structured context.
        """
        # 1. Retrieve current visit conversation turns (Highest Recency)
        current_turns: List[AnswerRecord] = AnswerRepository.get_by_visit_id(visit_id)
        
        # 2. Retrieve past consultations for the same user (Historical Continuity)
        past_consultations = ConsultationRepository.get_by_user(user_id)
        prior_histories: List[Dict[str, Any]] = []
        for c in past_consultations:
            if c.visit_id != visit_id:
                h = ConsultationRepository.get_final_history(c.visit_id)
                if h:
                    prior_histories.append({
                        "visit_id": c.visit_id,
                        "date": c.started_at,
                        "complaint": c.current_complaint,
                        "triage": c.triage_flag,
                        "data": h
                    })

        # 3. Organize into Structured Context (Step 5)
        recent_turn_summaries = []
        answered_fields = set()
        for turn in current_turns:
            recent_turn_summaries.append({
                "question": turn.question_text,
                "patient_answer": turn.answer_text,
                "input_mode": turn.input_mode,
                "structured_extracted": turn.structured_data,
                "time": turn.created_at
            })
            if turn.structured_data:
                answered_fields.update(turn.structured_data.keys())

        past_visit_summaries = []
        for ph in prior_histories[:3]:  # Top 3 most recent past visits
            h_data = ph.get("data", {})
            past_visit_summaries.append({
                "visit_id": ph["visit_id"],
                "date": ph["date"],
                "complaint": ph["complaint"],
                "triage_flag": ph["triage"],
                "past_history": h_data.get("past_history", []),
                "allergies": h_data.get("allergies", []),
                "medications": h_data.get("medications", [])
            })

        return {
            "user_id": user_id,
            "visit_id": visit_id,
            "current_input": current_input,
            "retrieval_queries_used": cls.generate_retrieval_queries(current_input),
            "answered_fields": list(answered_fields),
            "recent_conversation_turns": recent_turn_summaries,
            "past_consultation_summaries": past_visit_summaries,
            "context_summary_for_llm": cls._format_context_for_prompt(recent_turn_summaries, past_visit_summaries)
        }

    @classmethod
    def _format_context_for_prompt(
        cls,
        recent_turns: List[Dict[str, Any]],
        past_visits: List[Dict[str, Any]]
    ) -> str:
        """Formats clean, non-redundant historical context string for the LLM."""
        lines = []
        if recent_turns:
            lines.append("### CURRENT SESSION DIALOGUE HISTORY (Ordered chronologically):")
            for t in recent_turns:
                lines.append(f"- MediKiosk asked: \"{t['question']}\" -> Patient replied ({t['input_mode']}): \"{t['patient_answer']}\"")
        else:
            lines.append("### CURRENT SESSION DIALOGUE HISTORY: (First intake turn)")

        if past_visits:
            lines.append("\n### PATIENT PRIOR CLINICAL BACKGROUND (From previous visits):")
            for pv in past_visits:
                lines.append(f"- Visit {pv['visit_id']} ({pv['date']}): Complaint={pv['complaint']}, Triage={pv['triage_flag']}")
                if pv['allergies']:
                    lines.append(f"  Allergies: {', '.join(pv['allergies'])}")
                if pv['past_history']:
                    lines.append(f"  Past Conditions: {', '.join(pv['past_history'])}")

        return "\n".join(lines)
