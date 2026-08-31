import yaml
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ── 1. Models ─────────────────────────────────────────────────────────────────

LanguageCode = Literal["en", "te", "hi", "or"]
QuestionType = Literal["yes_no", "single_choice", "multiple_choice", "scale", "number", "text"]
TriageFlag = Literal["GREEN", "YELLOW", "RED"]

class LocalizedText(BaseModel):
    en: str
    te: Optional[str] = None
    hi: Optional[str] = None
    or_: Optional[str] = Field(default=None, alias="or")

    def get_for_lang(self, lang: str) -> str:
        if lang in ("or", "od", "or_"):
            return self.or_ or self.en
        val = getattr(self, lang, None)
        return val or self.en

class OptionChoice(BaseModel):
    value: str
    label: LocalizedText

class QuestionDefinition(BaseModel):
    field_name: str
    question: LocalizedText
    input_type: QuestionType
    required: bool = True
    priority: int = 10
    options: List[OptionChoice] = Field(default_factory=list)
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    section: str = "hpi"

class QuestionPrompt(BaseModel):
    field_name: str
    prompt_text: str
    input_type: QuestionType
    options: List[Dict[str, str]] = Field(default_factory=list)
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    progress_current: int = 1
    progress_total: int = 10
    section: str = "hpi"

class TriageResult(BaseModel):
    flag: TriageFlag = "GREEN"
    priority: bool = False
    reason_codes: List[str] = Field(default_factory=list)
    triggering_parameters: Dict[str, Any] = Field(default_factory=dict)
    evaluated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    recommendation: str = "Proceed with routine clinical consultation."

class ChiefComplaint(BaseModel):
    text: Optional[str] = None
    canonical: Optional[str] = None

class HPIState(BaseModel):
    duration_days: Optional[float] = None
    location: Optional[str] = None
    severity: Optional[int] = None
    character: Optional[str] = None
    radiation: Optional[str] = None
    aggravating_factors: List[str] = Field(default_factory=list)
    relieving_factors: List[str] = Field(default_factory=list)
    breathlessness: Optional[bool] = None
    sweating: Optional[bool] = None
    nausea: Optional[bool] = None
    dizziness: Optional[bool] = None
    fever: Optional[bool] = None
    cough: Optional[bool] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)

class ClinicalMetadata(BaseModel):
    completed: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    engine_version: str = "1.0"
    answered_fields: List[str] = Field(default_factory=list)

class ClinicalHistoryJSON(BaseModel):
    patient_id: str
    visit_id: str
    language: str = "en"
    chief_complaint: ChiefComplaint = Field(default_factory=ChiefComplaint)
    hpi: HPIState = Field(default_factory=HPIState)
    past_history: List[str] = Field(default_factory=list)
    past_surgical_history: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    family_history: List[str] = Field(default_factory=list)
    personal_history: Dict[str, Any] = Field(default_factory=dict)
    review_of_systems: Dict[str, Any] = Field(default_factory=dict)
    triage: TriageResult = Field(default_factory=TriageResult)
    metadata: ClinicalMetadata = Field(default_factory=ClinicalMetadata)


# ── 2. Symptom Loader ─────────────────────────────────────────────────────────

# Search for YAML symptom configs across candidate directories
# (supports both Part 3's own config and Part 1's config/symptoms directory)
def _find_symptoms_dir() -> Path:
    """Return the first directory that contains *.yaml symptom files."""
    here = Path(__file__).resolve()
    candidates = [
        # Part 3 local config (if someone adds YAML files here later)
        here.parents[4] / "config" / "symptoms",
        # Part 1's canonical symptom configs
        here.parents[4] / "part1" / "config" / "symptoms",
        # When running from project root
        Path("part1") / "config" / "symptoms",
        Path("part3") / "config" / "symptoms",
        # Part 3 inside its own directory tree
        here.parents[2] / "config" / "symptoms",
    ]
    for c in candidates:
        if c.exists() and any(c.glob("*.yaml")):
            return c
    # Return the Part 1 path as the expected default even if not yet found
    return here.parents[4] / "part1" / "config" / "symptoms"

SYMPTOMS_DIR = _find_symptoms_dir()

class SymptomLoader:
    _configs: Dict[str, dict] = {}

    @classmethod
    def load_all(cls) -> Dict[str, dict]:
        if cls._configs:
            return cls._configs

        if SYMPTOMS_DIR.exists():
            for yml in SYMPTOMS_DIR.glob("*.yaml"):
                try:
                    with open(yml, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data and "symptom" in data:
                            cls._configs[data["symptom"]] = data
                except Exception as e:
                    print(f"Error loading {yml}: {e}")
        return cls._configs

    @classmethod
    def match_symptom(cls, complaint_text: Optional[str]) -> str:
        if not complaint_text or not complaint_text.strip():
            return "general"

        t = complaint_text.lower().strip()
        configs = cls.load_all()

        if t in configs:
            return t

        for s_key, c_data in configs.items():
            canonicals = [c.lower() for c in c_data.get("canonical_names", [])]
            if t in canonicals or any(c in t for c in canonicals):
                return s_key

        if any(w in t for w in ["motion", "motions", "diarrhea", "loose", "విరేచనాలు", "మోషన్స్", "दस्त"]):
            return "diarrhea"
        if any(w in t for w in ["stomach", "abdominal", "belly", "కడుపు", "పేట్", "पेट"]):
            return "abdominal_pain"
        if any(w in t for w in ["chest", "cardiac", "గుండె", "ఛాతి", "छाती", "सीने"]):
            return "chest_pain"
        if any(w in t for w in ["fever", "temperature", "జ్వరం", "బుఖార్", "बुखार"]):
            return "fever"
        if any(w in t for w in ["headache", "head", "తలనొప్పి", "सिरदर्द"]):
            return "headache"
        if any(w in t for w in ["cough", "దగ్గు", "खांसी"]):
            return "cough"

        return "dynamic"

    @classmethod
    def get_questions_for_complaint(cls, complaint_text: Optional[str]) -> List[QuestionDefinition]:
        symptom_key = cls.match_symptom(complaint_text)
        configs = cls.load_all()

        if symptom_key == "dynamic" and complaint_text:
            return cls._build_dynamic_questionnaire(complaint_text)

        config = configs.get(symptom_key) or configs.get("general")
        q_list: List[QuestionDefinition] = []
        if not config:
            return q_list

        for q in config.get("questions", []):
            options = []
            for opt in q.get("options", []):
                options.append(OptionChoice(
                    value=str(opt["value"]),
                    label=LocalizedText(**opt["label"])
                ))
            q_list.append(QuestionDefinition(
                field_name=q["field_name"],
                question=LocalizedText(**q["question"]),
                input_type=q["input_type"],
                required=q.get("required", True),
                priority=q.get("priority", 10),
                options=options,
                min_val=q.get("min_val"),
                max_val=q.get("max_val"),
                section=q.get("section", "hpi")
            ))

        if symptom_key != "general":
            gen_cfg = configs.get("general_history")
            if gen_cfg:
                for gq in gen_cfg.get("questions", []):
                    options = []
                    for opt in gq.get("options", []):
                        options.append(OptionChoice(
                            value=str(opt["value"]),
                            label=LocalizedText(**opt["label"])
                        ))
                    q_list.append(QuestionDefinition(
                        field_name=gq["field_name"],
                        question=LocalizedText(**gq["question"]),
                        input_type=gq["input_type"],
                        required=gq.get("required", False),
                        priority=gq.get("priority", 20),
                        options=options,
                        section=gq.get("section", "past_history")
                    ))

        q_list.sort(key=lambda x: x.priority)
        return q_list

    @classmethod
    def _build_dynamic_questionnaire(cls, complaint_text: str) -> List[QuestionDefinition]:
        return [
            QuestionDefinition(
                field_name="duration_days",
                section="hpi",
                priority=1,
                required=True,
                input_type="number",
                min_val=0,
                max_val=365,
                question=LocalizedText(
                    en=f"How many days have you had this {complaint_text}?",
                    te=f"మీకు ఈ సమస్య ({complaint_text}) ఎన్ని రోజులుగా ఉంది?",
                    hi=f"आपको यह परेशानी ({complaint_text}) कितने दिनों से है?"
                )
            ),
            QuestionDefinition(
                field_name="severity",
                section="hpi",
                priority=2,
                required=True,
                input_type="scale",
                min_val=0,
                max_val=10,
                question=LocalizedText(
                    en=f"How severe is your {complaint_text} on a scale from 0 to 10?",
                    te=f"మీ సమస్య తీవ్రత 0 నుండి 10 వరకు ఎంత ఉంది?",
                    hi=f"आपकी परेशानी की तीव्रता 0 से 10 के पैमाने पर कितनी है?"
                )
            ),
            QuestionDefinition(
                field_name="fever",
                section="hpi",
                priority=3,
                required=True,
                input_type="yes_no",
                question=LocalizedText(
                    en="Do you have fever accompanying this problem?",
                    te="ఈ సమస్యతో పాటు మీకు జ్వరం ఉందా?",
                    hi="क्या इसके साथ बुखार भी है?"
                ),
                options=[
                    OptionChoice(value="true", label=LocalizedText(en="YES", te="అవును (Yes)", hi="हाँ (Yes)")),
                    OptionChoice(value="false", label=LocalizedText(en="NO", te="లేదు (No)", hi="नहीं (No)"))
                ]
            ),
            QuestionDefinition(
                field_name="breathlessness",
                section="hpi",
                priority=4,
                required=True,
                input_type="yes_no",
                question=LocalizedText(
                    en="Are you experiencing any difficulty in breathing or chest tightness?",
                    te="మీకు శ్వాస తీసుకోవడంలో ఇబ్బంది లేదా ఆయాసం ఉందా?",
                    hi="क्या आपको सांस लेने में कोई तकलीफ है?"
                ),
                options=[
                    OptionChoice(value="true", label=LocalizedText(en="YES", te="అవును (Yes)", hi="हाँ (Yes)")),
                    OptionChoice(value="false", label=LocalizedText(en="NO", te="లేదు (No)", hi="नहीं (No)"))
                ]
            )
        ]


# ── 3. Red Flag Rule Engine ────────────────────────────────────────────────────

class RedFlagRuleEngine:
    @staticmethod
    def evaluate(chief_complaint: str, hpi: HPIState, past_history: List[str] = None) -> TriageResult:
        complaint_lower = (chief_complaint or "").lower()
        reasons: List[str] = []
        triggering: Dict[str, Any] = {}

        if ("chest" in complaint_lower or "cardiac" in complaint_lower or "గుండె" in complaint_lower or "छाती" in complaint_lower):
            if hpi.breathlessness is True:
                reasons.append("CHEST_PAIN_WITH_BREATHLESSNESS")
                triggering["chief_complaint"] = chief_complaint
                triggering["breathlessness"] = True

            if (hpi.severity is not None and hpi.severity >= 7) and (hpi.sweating is True or (hpi.radiation and "arm" in str(hpi.radiation).lower())):
                reasons.append("SEVERE_CHEST_PAIN_WITH_AUTONOMIC_FEATURES")
                triggering["severity"] = hpi.severity
                triggering["sweating"] = hpi.sweating
                triggering["radiation"] = hpi.radiation

            if hpi.dizziness is True:
                reasons.append("CHEST_PAIN_WITH_SYNCOPE_DIZZINESS")
                triggering["dizziness"] = True

        if "fever" in complaint_lower or "జ్వరం" in complaint_lower or "बुखार" in complaint_lower:
            if hpi.breathlessness is True:
                reasons.append("FEVER_WITH_RESPIRATORY_DISTRESS")
                triggering["fever"] = True
                triggering["breathlessness"] = True

        if hpi.severity is not None and hpi.severity >= 8 and not reasons:
            return TriageResult(
                flag="YELLOW",
                priority=False,
                reason_codes=["SEVERE_PAIN_REQUIRING_PROMPT_EVALUATION"],
                triggering_parameters={"severity": hpi.severity},
                evaluated_at=datetime.now().isoformat(),
                recommendation="Priority queuing recommended for prompt clinical assessment."
            )

        if reasons:
            return TriageResult(
                flag="RED",
                priority=True,
                reason_codes=reasons,
                triggering_parameters=triggering,
                evaluated_at=datetime.now().isoformat(),
                recommendation="Priority clinical attention required. Alert triage nursing staff immediately."
            )

        return TriageResult(
            flag="GREEN",
            priority=False,
            reason_codes=[],
            triggering_parameters={},
            evaluated_at=datetime.now().isoformat(),
            recommendation="Proceed with standard clinical consultation workflow."
        )


# ── 4. Clinical Question Engine ────────────────────────────────────────────────

class ClinicalQuestionEngine:
    @classmethod
    def get_next_question(
        cls,
        history: ClinicalHistoryJSON,
        max_questions: int = 12
    ) -> Tuple[Optional[QuestionPrompt], bool]:
        triage = RedFlagRuleEngine.evaluate(
            chief_complaint=history.chief_complaint.canonical or history.chief_complaint.text or "",
            hpi=history.hpi,
            past_history=history.past_history
        )
        history.triage = triage
        if triage.flag == "RED" and triage.priority:
            return None, True

        complaint_text = history.chief_complaint.text
        if not complaint_text or not complaint_text.strip():
            general_questions = SymptomLoader.get_questions_for_complaint("general")
            if general_questions:
                q0 = general_questions[0]
                lang: str = history.language or "en"
                prompt_text = q0.question.get_for_lang(lang)
                return QuestionPrompt(
                    field_name=q0.field_name,
                    prompt_text=prompt_text,
                    input_type=q0.input_type,
                    options=[],
                    progress_current=1,
                    progress_total=6,
                    section="chief_complaint"
                ), False

        question_defs = SymptomLoader.get_questions_for_complaint(complaint_text)

        known_hpi = history.hpi.model_dump(exclude={"custom_fields"})
        known_hpi.update(history.hpi.custom_fields)
        answered_fields = set(history.metadata.answered_fields)

        missing_questions: List[QuestionDefinition] = []
        for q in question_defs:
            field = q.field_name
            section = q.section

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

            if val is None:
                missing_questions.append(q)

        if not missing_questions:
            return None, True

        missing_required = [q for q in missing_questions if q.required]
        next_q_def = missing_required[0] if missing_required else missing_questions[0]

        lang: str = history.language or "en"
        prompt_text = next_q_def.question.get_for_lang(lang)

        rendered_options = []
        for opt in next_q_def.options:
            opt_label = opt.label.get_for_lang(lang)
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


# ── 5. Session Coordinator ────────────────────────────────────────────────────

class RealHistoryEngine:
    _active_sessions: Dict[str, ClinicalHistoryJSON] = {}

    @classmethod
    def start_session(
        cls,
        patient_id: str,
        visit_id: str,
        language: str = "en",
        initial_complaint: Optional[str] = None
    ) -> Tuple[ClinicalHistoryJSON, Optional[QuestionPrompt]]:
        history = ClinicalHistoryJSON(
            patient_id=patient_id,
            visit_id=visit_id,
            language=language or "en",
            chief_complaint=ChiefComplaint(
                text=initial_complaint,
                canonical=initial_complaint.lower() if initial_complaint else None
            ),
            metadata=ClinicalMetadata(completed=False)
        )
        if initial_complaint:
            history.triage = RedFlagRuleEngine.evaluate(
                chief_complaint=history.chief_complaint.canonical or "",
                hpi=history.hpi,
                past_history=history.past_history
            )
        cls._active_sessions[visit_id] = history
        prompt, is_comp = ClinicalQuestionEngine.get_next_question(history)
        if is_comp or (history.triage.flag == "RED" and history.triage.priority):
            history.metadata.completed = True
        return history, prompt

    @classmethod
    def get_session(cls, visit_id: str) -> Optional[ClinicalHistoryJSON]:
        return cls._active_sessions.get(visit_id)

    @classmethod
    def process_message(
        cls,
        visit_id: str,
        patient_message: str,
        target_field: Optional[str] = None,
        is_touch_input: bool = False,
        touch_value: Optional[str] = None,
        language: str = "en"
    ) -> Tuple[ClinicalHistoryJSON, Optional[QuestionPrompt], bool]:
        history = cls.get_session(visit_id)
        if not history:
            history, _ = cls.start_session(patient_id="PAT-000001", visit_id=visit_id, language=language)

        if language:
            history.language = language

        # Update Chief Complaint if not set
        if not history.chief_complaint.text:
            history.chief_complaint.text = patient_message
            history.chief_complaint.canonical = patient_message.lower().strip()
            history.metadata.answered_fields.append("chief_complaint")

        # Mark target field answered
        if target_field and target_field not in history.metadata.answered_fields:
            history.metadata.answered_fields.append(target_field)

        # Apply value to HPI / Past History
        msg_low = (touch_value or patient_message).lower().strip()
        hpi_dict = history.hpi.model_dump()

        if target_field == "duration_days":
            m = re.search(r"\b(\d+)\b", msg_low)
            if m:
                hpi_dict["duration_days"] = float(m.group(1))
            elif "yesterday" in msg_low or "నిన్న" in msg_low or "कल" in msg_low:
                hpi_dict["duration_days"] = 1.0
            else:
                hpi_dict["duration_days"] = 3.0
        elif target_field == "severity":
            m = re.search(r"\b([0-9]|10)\b", msg_low)
            if m:
                hpi_dict["severity"] = int(m.group(1))
            else:
                hpi_dict["severity"] = 5
        elif target_field in ["breathlessness", "sweating", "nausea", "dizziness", "fever", "cough"]:
            is_yes = any(w in msg_low for w in ["yes", "true", "అవును", "हाँ", "1"])
            hpi_dict[target_field] = is_yes
        elif target_field == "diabetes_hypertension":
            if any(w in msg_low for w in ["yes", "diabetes", "hypertension", "bp", "sugar"]):
                history.past_history.append(patient_message)
            else:
                history.past_history.append("none")
        elif target_field == "drug_allergies":
            if not any(w in msg_low for w in ["no", "none", "లేదు", "లేవు", "नहीं"]):
                history.allergies.append(patient_message)
            else:
                history.allergies.append("none")
        elif target_field == "regular_medications":
            if not any(w in msg_low for w in ["no", "none", "లేదు", "లేవు", "नहीं"]):
                history.medications.append(patient_message)
            else:
                history.medications.append("none")
        elif target_field:
            hpi_dict[target_field] = touch_value or patient_message

        history.hpi = HPIState(**hpi_dict)

        # Check Red-Flag triage
        triage = RedFlagRuleEngine.evaluate(
            chief_complaint=history.chief_complaint.canonical or history.chief_complaint.text or "",
            hpi=history.hpi,
            past_history=history.past_history
        )
        history.triage = triage

        # Determine next question
        prompt, is_completed = ClinicalQuestionEngine.get_next_question(history)

        if is_completed or (triage.flag == "RED" and triage.priority):
            history.metadata.completed = True
            is_completed = True

        cls._active_sessions[visit_id] = history
        return history, prompt, is_completed
