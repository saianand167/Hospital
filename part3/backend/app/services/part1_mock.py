from typing import Dict, Any

class Part1HistoryEngineMock:
    @staticmethod
    def generate_clinical_history(
        patient_id: str, 
        visit_id: str, 
        chief_complaint_text: str = "Chest pain",
        is_red_flag: bool = False
    ) -> Dict[str, Any]:
        """
        Simulate Part 1 output JSON structure.
        """
        priority = "HIGH" if (is_red_flag or "chest pain" in chief_complaint_text.lower() or "breathlessness" in chief_complaint_text.lower()) else "NORMAL"
        
        return {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "chief_complaint": {
                "complaint": chief_complaint_text,
                "duration": "4 days",
                "severity": "7/10" if priority == "HIGH" else "4/10"
            },
            "hpi": {
                "onset": "Gradual",
                "character": "Squeezing / Pressure" if priority == "HIGH" else "Dull ache",
                "radiation": "Left arm" if priority == "HIGH" else "None",
                "associated_symptoms": ["Breathlessness", "Diaphoresis"] if priority == "HIGH" else ["Mild fatigue"]
            },
            "past_history": {
                "hypertension": True if priority == "HIGH" else False,
                "diabetes": False,
                "previous_episodes": "Similar mild pain 6 months ago"
            },
            "medications": ["Aspirin 75mg daily"] if priority == "HIGH" else [],
            "allergies": ["Penicillin"],
            "family_history": {
                "cad": "Father had MI at age 55"
            },
            "personal_history": {
                "smoking": "Non-smoker",
                "alcohol": "Occasional"
            },
            "review_of_systems": {
                "cardiovascular": "Positive for chest discomfort",
                "respiratory": "Mild shortness of breath" if priority == "HIGH" else "Normal"
            },
            "triage": {
                "priority": priority,
                "red_flag_detected": priority == "HIGH",
                "reason": "Chest pain radiating to left arm with breathlessness" if priority == "HIGH" else "Standard routine consultation"
            }
        }
