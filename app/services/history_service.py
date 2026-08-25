from typing import Dict, Optional, Tuple, List
from datetime import datetime
import re
from app.models.history import ClinicalHistoryJSON, HPIState, ChiefComplaint, ClinicalMetadata
from app.models.question import QuestionPrompt
from app.models.patient import LanguageCode
from app.models.answer import AnswerRecord
from app.clinical.question_engine import ClinicalQuestionEngine
from app.clinical.triage_rules import RedFlagRuleEngine
from app.clinical.history_aware_retriever import HistoryAwareRetriever
from app.llm.extraction import ClinicalExtractor
from app.asr.indic_asr import IndicASR
from app.repositories.consultation_repository import ConsultationRepository
from app.repositories.answer_repository import AnswerRepository

class HistoryService:
    """
    Session coordinator with Database Persistence & History-Aware Conversation Retrieval.
    Maintains isolated consultation states, retrieves history with recency weighting,
    and guarantees forward progress on all positive and negative answers.
    """
    _active_sessions: Dict[str, ClinicalHistoryJSON] = {}
    _asr_provider = IndicASR()

    @classmethod
    def start_session(
        cls,
        user_id: str = "USR-000001",
        visit_id: Optional[str] = None,
        language: LanguageCode = "en",
        initial_complaint: Optional[str] = None
    ) -> Tuple[ClinicalHistoryJSON, Optional[QuestionPrompt]]:
        if not visit_id:
            visit_id = ConsultationRepository.create_consultation(user_id=user_id, language=language, complaint=initial_complaint)

        history = ClinicalHistoryJSON(
            patient_id=user_id,
            visit_id=visit_id,
            language=language,
            chief_complaint=ChiefComplaint(
                text=initial_complaint,
                canonical=initial_complaint.lower() if initial_complaint else None
            ),
            metadata=ClinicalMetadata(completed=False)
        )
        cls._active_sessions[visit_id] = history
        
        prompt, is_comp = ClinicalQuestionEngine.get_next_question(history)
        if is_comp:
            history.metadata.completed = True
            cls._finalize_session(history)
            
        return history, prompt

    @classmethod
    def get_session(cls, visit_id: str) -> Optional[ClinicalHistoryJSON]:
        if visit_id in cls._active_sessions:
            return cls._active_sessions[visit_id]
        
        db_history = ConsultationRepository.get_final_history(visit_id)
        if db_history:
            return ClinicalHistoryJSON(**db_history)
        return None

    @classmethod
    async def process_message(
        cls,
        visit_id: str,
        patient_message: str,
        target_field: Optional[str] = None,
        is_touch_input: bool = False,
        touch_value: Optional[str] = None,
        question_text: Optional[str] = None,
        input_mode: str = "text"
    ) -> Tuple[ClinicalHistoryJSON, Optional[QuestionPrompt], bool]:
        history = cls.get_session(visit_id)
        if not history:
            history, _ = cls.start_session(visit_id=visit_id)

        # Mark target field as answered to guarantee the interview moves forward
        if target_field and target_field not in history.metadata.answered_fields:
            history.metadata.answered_fields.append(target_field)

        # 1. Step 1 to 5: Run History-Aware Conversation Retrieval
        hist_context = HistoryAwareRetriever.retrieve_historical_context(
            user_id=history.patient_id,
            visit_id=visit_id,
            current_input=patient_message
        )
        context_str = hist_context.get("context_summary_for_llm", "")

        # 2. Apply Touch or Extract via History-Aware LLM Pipeline
        if is_touch_input and target_field and touch_value is not None:
            cls._apply_touch_input(history, target_field, touch_value)
            extracted_dict = {target_field: touch_value}
        else:
            # Handle direct negative / "no" / "none" answers when asked a specific target field
            msg_lower = patient_message.lower().strip()
            is_negative_ans = any(w in msg_lower for w in ["no", "none", "nothing", "లేదు", "లేవు", "ఏమీ లేవు", "नहीं", "कुछ नहीं", "na", "nill"])
            
            if target_field and is_negative_ans:
                cls._apply_touch_input(history, target_field, "none")
                extracted_dict = {target_field: "none"}
            else:
                history = await ClinicalExtractor.extract_and_update(
                    patient_text=patient_message,
                    history=history,
                    target_field=target_field,
                    history_context_str=context_str
                )
                # If target field wasn't set by extraction, set safe fallback
                cls._ensure_target_field_populated(history, target_field, patient_message)
                extracted_dict = history.hpi.model_dump(exclude_none=True)

        # Update chief complaint in DB if newly extracted
        if history.chief_complaint.text:
            ConsultationRepository.update_complaint(visit_id, history.chief_complaint.text)

        # 3. Persist Answer Record in Database
        AnswerRepository.save_answer(
            visit_id=visit_id,
            user_id=history.patient_id,
            question_text=question_text or target_field or "Consultation Intake",
            answer_text=patient_message,
            input_mode="touch" if is_touch_input else input_mode,
            language=history.language,
            structured_data=extracted_dict
        )

        # 4. Deterministic Red-Flag Triage Check
        triage = RedFlagRuleEngine.evaluate(
            chief_complaint=history.chief_complaint.canonical or history.chief_complaint.text or "",
            hpi=history.hpi,
            past_history=history.past_history
        )
        history.triage = triage

        # 5. Next Question Selection
        prompt, is_completed = ClinicalQuestionEngine.get_next_question(history)
        if is_completed or (triage.flag == "RED" and triage.priority):
            history.metadata.completed = True
            is_completed = True
            cls._finalize_session(history)

        cls._active_sessions[visit_id] = history
        return history, prompt, is_completed

    @classmethod
    def _ensure_target_field_populated(cls, history: ClinicalHistoryJSON, target_field: Optional[str], text: str):
        """Ensures that the specific field being asked receives a value from the user's message."""
        if not target_field:
            return

        t_low = text.lower().strip()
        hpi_dict = history.hpi.model_dump()

        if target_field == "duration_days" and hpi_dict.get("duration_days") is None:
            m = re.search(r"\b(\d+)\b", t_low)
            if m:
                hpi_dict["duration_days"] = float(m.group(1))
            elif "yesterday" in t_low or "నిన్న" in t_low or "कल" in t_low:
                hpi_dict["duration_days"] = 1.0
        elif target_field == "severity" and hpi_dict.get("severity") is None:
            m = re.search(r"\b([0-9]|10)\b", t_low)
            if m:
                hpi_dict["severity"] = int(m.group(1))
        elif target_field == "location" and hpi_dict.get("location") is None:
            hpi_dict["location"] = text
        elif target_field == "diabetes_hypertension":
            if not history.past_history:
                history.past_history.append("none" if any(w in t_low for w in ["no", "none", "లేదు", "లేవు", "नहीं"]) else text)
        elif target_field == "drug_allergies":
            if not history.allergies:
                history.allergies.append("none" if any(w in t_low for w in ["no", "none", "లేదు", "లేవు", "नहीं"]) else text)
        elif target_field == "regular_medications":
            if not history.medications:
                history.medications.append("none" if any(w in t_low for w in ["no", "none", "లేదు", "లేవు", "नहीं"]) else text)

        history.hpi = HPIState(**hpi_dict)

    @classmethod
    async def process_audio(
        cls,
        visit_id: str,
        audio_bytes: bytes,
        target_field: Optional[str] = None,
        question_text: Optional[str] = None
    ) -> Tuple[str, ClinicalHistoryJSON, Optional[QuestionPrompt], bool]:
        history = cls.get_session(visit_id)
        lang = history.language if history else "en"
        
        transcribed_text = await cls._asr_provider.transcribe(audio_bytes, language=lang)
        
        history, prompt, is_completed = await cls.process_message(
            visit_id=visit_id,
            patient_message=transcribed_text,
            target_field=target_field,
            question_text=question_text,
            input_mode="voice"
        )
        return transcribed_text, history, prompt, is_completed

    @classmethod
    def _apply_touch_input(cls, history: ClinicalHistoryJSON, field_name: str, value: str):
        val_lower = str(value).lower().strip()
        hpi_dict = history.hpi.model_dump()
        
        if val_lower in ["true", "yes", "అవును", "हाँ", "1"]:
            hpi_dict[field_name] = True
        elif val_lower in ["false", "no", "లేదు", "లేవు", "नहीं", "0", "none"]:
            if field_name in ["diabetes_hypertension"]:
                if "none" not in history.past_history:
                    history.past_history.append("none")
            elif field_name in ["drug_allergies"]:
                if "none" not in history.allergies:
                    history.allergies.append("none")
            elif field_name in ["regular_medications"]:
                if "none" not in history.medications:
                    history.medications.append("none")
            else:
                hpi_dict[field_name] = False
        elif val_lower.isdigit():
            if field_name == "severity":
                hpi_dict[field_name] = max(0, min(10, int(val_lower)))
            elif field_name == "duration_days":
                hpi_dict[field_name] = float(val_lower)
            else:
                hpi_dict[field_name] = val_lower
        elif field_name == "diabetes_hypertension":
            if val_lower != "none" and val_lower not in history.past_history:
                history.past_history.append(val_lower)
            elif val_lower == "none":
                history.past_history.append("none")
        elif field_name == "drug_allergies":
            if val_lower != "none" and val_lower not in history.allergies:
                history.allergies.append(val_lower)
            elif val_lower == "none":
                history.allergies.append("none")
        elif field_name == "regular_medications":
            if val_lower != "none" and val_lower not in history.medications:
                history.medications.append(val_lower)
            elif val_lower == "none":
                history.medications.append("none")
        else:
            hpi_dict[field_name] = value

        history.hpi = HPIState(**hpi_dict)

    @classmethod
    def _finalize_session(cls, history: ClinicalHistoryJSON):
        history.metadata.completed = True
        status = "escalated" if (history.triage.flag == "RED" and history.triage.priority) else "completed"
        
        ConsultationRepository.update_triage_and_status(
            visit_id=history.visit_id,
            status=status,
            flag=history.triage.flag,
            priority=history.triage.priority,
            completed=True
        )
        ConsultationRepository.save_final_history(
            visit_id=history.visit_id,
            user_id=history.patient_id,
            history_dict=history.model_dump()
        )

    @classmethod
    def complete_session(cls, visit_id: str) -> Optional[ClinicalHistoryJSON]:
        history = cls.get_session(visit_id)
        if history:
            cls._finalize_session(history)
        return history

    @classmethod
    def get_conversation_history(cls, visit_id: str) -> List[AnswerRecord]:
        return AnswerRepository.get_by_visit_id(visit_id)
