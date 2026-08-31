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
                    en="Do you have fever, chills, or high body temperature?",
                    te="ఈ సమస్యతో పాటు మీకు జ్వరం లేదా చలిగా ఉందా?",
                    hi="क्या आपको बुखार, ठंड या तेज तापमान है?"
                ),
                options=[
                    OptionChoice(value="true", label=LocalizedText(en="YES (Fever)", te="అవును (జ్వరం ఉంది)", hi="हाँ (बुखार है)")),
                    OptionChoice(value="false", label=LocalizedText(en="NO (No Fever)", te="లేదు (జ్వరం లేదు)", hi="नहीं (बुखार नहीं है)"))
                ]
            ),
            QuestionDefinition(
                field_name="cough",
                section="hpi",
                priority=4,
                required=True,
                input_type="yes_no",
                question=LocalizedText(
                    en="Do you have cough, throat irritation, or cold symptoms?",
                    te="మీకు దగ్గు, గొంతు నొప్పి లేదా జలుబు ఉందా?",
                    hi="क्या आपको खांसी, गले में खराश या जुकाम है?"
                ),
                options=[
                    OptionChoice(value="true", label=LocalizedText(en="YES (Cough/Cold)", te="అవును (దగ్గు/జలుబు ఉంది)", hi="हाँ (खांसी/जुकाम है)")),
                    OptionChoice(value="false", label=LocalizedText(en="NO", te="లేదు", hi="नहीं"))
                ]
            ),
            QuestionDefinition(
                field_name="breathlessness",
                section="hpi",
                priority=5,
                required=True,
                input_type="yes_no",
                question=LocalizedText(
                    en="Are you experiencing any shortness of breath or difficulty breathing?",
                    te="మీకు శ్వాస తీసుకోవడంలో ఇబ్బంది లేదా ఆయాసం ఉందా?",
                    hi="क्या आपको सांस लेने में कोई तकलीफ है?"
                ),
                options=[
                    OptionChoice(value="true", label=LocalizedText(en="YES (Breathing Issue)", te="అవును (శ్వాస ఇబ్బంది ఉంది)", hi="हाँ (सांस लेने में तकलीफ है)")),
                    OptionChoice(value="false", label=LocalizedText(en="NO", te="లేదు (No)", hi="नहीं (No)"))
                ]
            ),
            QuestionDefinition(
                field_name="diabetes_hypertension",
                section="past_history",
                priority=6,
                required=True,
                input_type="text",
                question=LocalizedText(
                    en="Do you have any past medical history (e.g. Diabetes, BP, Heart disease, Asthma)?",
                    te="మీకు గతంలో షుగర్ (డయాబెటిస్), రక్తపోటు (BP), గుండె జబ్బులు లేదా ఆస్తమా ఉన్నాయా?",
                    hi="क्या आपको पहले से कोई बीमारी जैसे शुगर, बीपी, हृदय रोग या अस्थमा है?"
                ),
                options=[
                    OptionChoice(value="none", label=LocalizedText(en="No Prior Diseases", te="ఏమీ లేవు (None)", hi="कोई बीमारी नहीं")),
                    OptionChoice(value="diabetes", label=LocalizedText(en="Diabetes (Sugar)", te="షుగర్ (Diabetes)", hi="डायबिटीज")),
                    OptionChoice(value="hypertension", label=LocalizedText(en="Hypertension (BP)", te="బీపీ (BP)", hi="हाई बीपी")),
                    OptionChoice(value="both", label=LocalizedText(en="Both BP & Sugar", te="షుగర్ & బీపీ రెండూ", hi="शुगर और बीपी दोनों"))
                ]
            ),
            QuestionDefinition(
                field_name="regular_medications",
                section="medications",
                priority=7,
                required=True,
                input_type="text",
                question=LocalizedText(
                    en="Are you currently taking any regular daily medications?",
                    te="మీరు ప్రస్తుతం ఏవైనా రోజువారీ మందులు లేదా మాత్రలు వాడుతున్నారా?",
                    hi="क्या आप वर्तमान में कोई नियमित दवाएं ले रहे हैं?"
                ),
                options=[
                    OptionChoice(value="none", label=LocalizedText(en="No Medications", te="మందులు వాడట్లేదు (None)", hi="कोई दवा नहीं")),
                    OptionChoice(value="bp_sugar_meds", label=LocalizedText(en="BP / Sugar Meds", te="బీపీ / షుగర్ మాత్రలు", hi="बीपी / शुगर की दवा")),
                    OptionChoice(value="antibiotics", label=LocalizedText(en="Antibiotics / Painkillers", te="యాంటీబయాటిక్స్ / మాత్రలు", hi="एंटीबायोटिक दवाएं"))
                ]
            ),
            QuestionDefinition(
                field_name="drug_allergies",
                section="allergies",
                priority=8,
                required=True,
                input_type="text",
                question=LocalizedText(
                    en="Do you have any known drug or medication allergies?",
                    te="మీకు ఏదైనా మందులు లేదా ఇంజెక్షన్ల వల్ల అలర్జీలు ఉన్నాయా?",
                    hi="क्या आपको किसी दवा से कोई एलर्जी है?"
                ),
                options=[
                    OptionChoice(value="none", label=LocalizedText(en="No Known Allergies", te="ఎలాంటి అలర్జీలు లేవు (None)", hi="कोई एलर्जी नहीं")),
                    OptionChoice(value="penicillin", label=LocalizedText(en="Penicillin Allergy", te="పెన్సిలిన్ అలర్జీ", hi="पेनिसिलिन एलर्जी")),
                    OptionChoice(value="sulfa", label=LocalizedText(en="Sulfa / Other Drugs", te="సల్ఫా / ఇతర అలర్జీలు", hi="सल्फा दवाएं"))
                ]
            )
        ]
