from typing import Optional, List, Dict, Any, Tuple
from app.models.question import QuestionDefinition, QuestionPrompt
from app.models.history import ClinicalHistoryJSON, HPIState
from app.models.patient import LanguageCode
from app.clinical.symptom_loader import SymptomLoader
from app.clinical.triage_rules import RedFlagRuleEngine

class ClinicalQuestionEngine:
    """
    Deterministic clinical question selection & state engine.
    Never assumes chest pain; starts with general intake and dynamically adapts.
    Guarantees state progress without getting stuck on negative or empty answers!
    """
    
    @classmethod
    def get_next_question(
        cls,
        history: ClinicalHistoryJSON,
        max_questions: int = 12
    ) -> Tuple[Optional[QuestionPrompt], bool]:
        """
        Returns (next_question_prompt, is_completed)
        """
        # 1. Red-Flag safety check
        triage = RedFlagRuleEngine.evaluate(
            chief_complaint=history.chief_complaint.canonical or history.chief_complaint.text or "",
            hpi=history.hpi,
            past_history=history.past_history
        )
        history.triage = triage
        if triage.flag == "RED" and triage.priority:
            return None, True

        # 2. Check if Chief Complaint is known
        complaint_text = history.chief_complaint.text
        if not complaint_text or not complaint_text.strip():
            # First question MUST be general: "What are you suffering from?"
            general_questions = SymptomLoader.get_questions_for_complaint("general")
            if general_questions:
                q0 = general_questions[0]
                lang: LanguageCode = history.language or "en"
                prompt_text = getattr(q0.question, lang, None) or q0.question.en
                return QuestionPrompt(
                    field_name=q0.field_name,
                    prompt_text=prompt_text,
                    input_type=q0.input_type,
                    options=[],
                    progress_current=1,
                    progress_total=6,
                    section="chief_complaint"
                ), False

        # 3. Dynamic questionnaire based on patient's current complaint
        question_defs = SymptomLoader.get_questions_for_complaint(complaint_text)
        
        known_hpi = history.hpi.model_dump(exclude={"custom_fields"})
        known_hpi.update(history.hpi.custom_fields)
        answered_fields = set(history.metadata.answered_fields)
        
        missing_questions: List[QuestionDefinition] = []
        for q in question_defs:
            field = q.field_name
            section = q.section
            
            # If explicitly marked answered, skip!
            if field in answered_fields:
                continue

            val = None
            if section == "hpi":
                val = known_hpi.get(field)
            elif section == "past_history":
                val = history.past_history if len(history.past_history) > 0 else None
            elif section == "allergies":
                val = history.allergies if len(history.allergies) > 0 else None
            elif section == "medications":
                val = history.medications if len(history.medications) > 0 else None

            # Missing if None (explicit false / 0 are known!)
            if val is None:
                missing_questions.append(q)

        if not missing_questions:
            return None, True

        # Prioritize required missing fields
        missing_required = [q for q in missing_questions if q.required]
        next_q_def = missing_required[0] if missing_required else missing_questions[0]
        
        # Localized prompt text in patient's selected language
        lang: LanguageCode = history.language or "en"
        prompt_text = getattr(next_q_def.question, lang, None) or next_q_def.question.en
        
        rendered_options = []
        for opt in next_q_def.options:
            opt_label = getattr(opt.label, lang, None) or opt.label.en
            rendered_options.append({
                "value": opt.value,
                "label": opt_label
            })

        total_q_count = len(question_defs)
        answered_count = total_q_count - len(missing_questions)
        
        prompt = QuestionPrompt(
            field_name=next_q_def.field_name,
            prompt_text=prompt_text,
            input_type=next_q_def.input_type,
            options=rendered_options,
            min_val=next_q_def.min_val,
            max_val=next_q_def.max_val,
            progress_current=min(total_q_count, answered_count + 1),
            progress_total=max(1, total_q_count),
            section=next_q_def.section
        )
        
        return prompt, False
