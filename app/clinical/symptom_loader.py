import yaml
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import settings
from app.models.question import QuestionDefinition, LocalizedText, OptionChoice

class SymptomLoader:
    _configs: Dict[str, dict] = {}

    @classmethod
    def load_all(cls) -> Dict[str, dict]:
        if cls._configs:
            return cls._configs
        
        symptoms_dir = settings.SYMPTOMS_DIR
        if not symptoms_dir.exists():
            return {}
            
        for yml in symptoms_dir.glob("*.yaml"):
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
        """
        Dynamically matches free-form text or extracted complaint to canonical symptom key.
        If empty or unstated, returns 'general'.
        """
        if not complaint_text or not complaint_text.strip():
            return "general"

        t = complaint_text.lower().strip()
        configs = cls.load_all()

        # Check exact key
        if t in configs:
            return t

        # Check canonical names across all configs
        for s_key, c_data in configs.items():
            canonicals = [c.lower() for c in c_data.get("canonical_names", [])]
            if t in canonicals or any(c in t for c in canonicals):
                return s_key

        # Substring heuristics
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

        # If it's a known complaint text that doesn't match a static yaml, return 'dynamic'
        return "dynamic"

    @classmethod
    def get_questions_for_complaint(cls, complaint_text: Optional[str]) -> List[QuestionDefinition]:
        symptom_key = cls.match_symptom(complaint_text)
        configs = cls.load_all()

        # If dynamic complaint (e.g. back pain, dizziness, allergy), generate standard clinical questionnaire
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

        # Append general history questions (Past History, Allergies, Meds) only if symptom is specific
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
        """Dynamically generates standard clinical HPI questions for any unlisted symptom."""
        c_title = complaint_text.title()
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
