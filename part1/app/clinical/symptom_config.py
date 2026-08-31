import yaml
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import settings
from app.models.question import QuestionDefinition, LocalizedText, OptionChoice

class SymptomConfigLoader:
    _configs: Dict[str, dict] = {}
    
    @classmethod
    def load_all(cls) -> Dict[str, dict]:
        if cls._configs:
            return cls._configs
        
        symptoms_dir = settings.SYMPTOMS_DIR
        if not symptoms_dir.exists():
            return {}
        
        for yml_file in symptoms_dir.glob("*.yaml"):
            try:
                with open(yml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and "symptom" in data:
                        cls._configs[data["symptom"]] = data
            except Exception as e:
                print(f"Error loading symptom config {yml_file}: {e}")
        return cls._configs

    @classmethod
    def get_symptom_config(cls, symptom_name: str) -> Optional[dict]:
        configs = cls.load_all()
        # Exact match
        if symptom_name in configs:
            return configs[symptom_name]
        
        # Canonical names match
        s_lower = symptom_name.lower().strip()
        for s_key, c_data in configs.items():
            canonicals = [c.lower() for c in c_data.get("canonical_names", [])]
            if s_lower in canonicals or s_lower == s_key:
                return c_data
            for c in canonicals:
                if c in s_lower or s_lower in c:
                    return c_data
        
        # Default to chest_pain if chief complaint is cardiac or chest
        if "chest" in s_lower or "నొప్పి" in s_lower or "दर्द" in s_lower or "pain" in s_lower:
            return configs.get("chest_pain")
        if "fever" in s_lower or "జ్వరం" in s_lower or "बुखार" in s_lower:
            return configs.get("fever")
            
        return configs.get("chest_pain")

    @classmethod
    def get_questions_for_symptom(cls, symptom_name: str) -> List[QuestionDefinition]:
        config = cls.get_symptom_config(symptom_name)
        if not config:
            return []
        
        q_list: List[QuestionDefinition] = []
        raw_questions = config.get("questions", [])
        for q in raw_questions:
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
            
        # Append general history questions if available
        general_cfg = cls.load_all().get("general_history")
        if general_cfg:
            for gq in general_cfg.get("questions", []):
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
                
        # Sort by priority
        q_list.sort(key=lambda x: x.priority)
        return q_list
