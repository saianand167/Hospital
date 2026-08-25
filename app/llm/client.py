import json
import httpx
import re
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.logging_config import logger

class LLMClient:
    """
    Unified LLM Client connecting to Groq (GPT-OSS-120B / Qwen) and Grok (xAI) with deterministic mock fallback.
    """
    
    @classmethod
    def get_model_status(cls) -> Dict[str, str]:
        """Returns the active LLM provider and status badge."""
        if settings.MOCK_MODE:
            return {"provider": "Offline Mock", "status": "MOCK MODE", "badge_color": "#64748b"}
        if settings.GROQ_API_KEY:
            return {"provider": "Groq LLM", "model": "openai/gpt-oss-120b", "status": "CONNECTED", "badge_color": "#10b981"}
        if settings.GROK_API_KEY:
            return {"provider": "xAI Grok", "model": "grok-beta", "status": "CONNECTED", "badge_color": "#10b981"}
        return {"provider": "Deterministic Engine", "status": "ACTIVE", "badge_color": "#0d9488"}

    @classmethod
    async def generate_completion(
        cls,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        response_format: Optional[str] = "json_object"
    ) -> Optional[str]:
        if settings.MOCK_MODE:
            return cls._mock_response(user_prompt)

        # 1. Attempt Groq API (High-speed Llama / GPT-OSS)
        if settings.GROQ_API_KEY:
            models_to_try = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]
            for model_name in models_to_try:
                try:
                    headers = {
                        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temperature,
                        "response_format": {"type": "json_object"}
                    }
                    async with httpx.AsyncClient(timeout=12.0) as client:
                        resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            content = data["choices"][0]["message"]["content"]
                            if content and content.strip():
                                return content
                except Exception as e:
                    logger.warning(f"Groq {model_name} call failed: {e}")

        # 2. Attempt Grok API (xAI)
        if settings.GROK_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.GROK_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "grok-beta",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": temperature,
                    "stream": False
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"Grok API call failed: {e}")

        # 3. Fallback to offline deterministic rule-based extractor
        return cls._mock_response(user_prompt)

    @classmethod
    def _mock_response(cls, user_prompt: str) -> str:
        """
        Deterministic, rule-based extraction fallback for offline / mock testing.
        Extracts solely from patient text section, guaranteeing zero hallucinations!
        """
        match = re.search(r'Patient Response:\s*"(.*?)"', user_prompt, re.DOTALL)
        if match:
            text = match.group(1).strip()
        else:
            text = user_prompt.strip()

        t_lower = text.lower()
        extracted: Dict[str, Any] = {
            "chief_complaint": None,
            "duration_days": None,
            "location": None,
            "severity": None,
            "character": None,
            "radiation": None,
            "breathlessness": None,
            "sweating": None,
            "dizziness": None,
            "vomiting": None,
            "fever": None,
            "cough": None,
            "past_history": [],
            "medications": [],
            "allergies": []
        }

        # 1. Chief Complaint Extraction
        if any(w in t_lower for w in ["motion", "motions", "diarrhea", "loose motion", "loose stool", "విరేచనాలు", "మోషన్స్", "దస్తీలు", "दस्त", "लूज मोशन"]):
            extracted["chief_complaint"] = "diarrhea"
        elif any(w in t_lower for w in ["stomach pain", "abdominal pain", "belly pain", "కడుపు నొప్పి", "కడుపులో నొప్పి", "కడుపు", "पेट दर्द", "पेट में दर्द", "पेट"]):
            extracted["chief_complaint"] = "abdominal pain"
        elif any(w in t_lower for w in ["chest pain", "chest tightness", "chest", "గుండె నొప్పి", "ఛాతి నొప్పి", "ఛాతి", "గుండె", "सीने में दर्द", "छाती में दर्द", "सीने", "छाती"]):
            extracted["chief_complaint"] = "chest pain"
        elif any(w in t_lower for w in ["fever", "high temp", "temperature", "జ్వరం", "బుఖార్", "బుఖార్ ఉంది", "बुखार"]):
            extracted["chief_complaint"] = "fever"
        elif any(w in t_lower for w in ["headache", "head pain", "తలనొప్పి", "తల నొప్పి", "सिरदर्द", "सिर में दर्द"]):
            extracted["chief_complaint"] = "headache"
        elif any(w in t_lower for w in ["cough", "dry cough", "దగ్గు", "खांसी"]):
            extracted["chief_complaint"] = "cough"
        else:
            # If free text has a complaint, preserve it
            cleaned = re.sub(r'^(i am having|i have|i got|suffering from|getting)\s+', '', t_lower).strip()
            if len(cleaned) > 2 and len(cleaned.split()) <= 4:
                extracted["chief_complaint"] = cleaned

        # 2. Duration Detection
        duration_match = re.search(r"(\d+)\s*(days?|day|రోజులు|రోజులుగా|दिन|दिनों)", t_lower)
        if duration_match:
            extracted["duration_days"] = float(duration_match.group(1))
        elif any(w in t_lower for w in ["four days", "నాలుగు రోజులుగా", "నాలుగు రోజులు", "चार दिन", "चार दिनों"]):
            extracted["duration_days"] = 4.0
        elif any(w in t_lower for w in ["three days", "మూడు రోజులుగా", "మూడు రోజులు", "तीन दिन", "तीन दिनों"]):
            extracted["duration_days"] = 3.0
        elif any(w in t_lower for w in ["two days", "రెండు రోజులుగా", "రెండు రోజులు", "दो दिन", "दो दिनों"]):
            extracted["duration_days"] = 2.0
        elif any(w in t_lower for w in ["one day", "yesterday", "నిన్నటి నుండి", "ఒక రోజు", "कल से", "एक दिन"]):
            extracted["duration_days"] = 1.0

        # 3. Location Detection
        if any(w in t_lower for w in ["right lower", "right", "కుడి వైపు", "కుడి", "दाईं", "दाएं", "दायां"]):
            extracted["location"] = "right"
        elif any(w in t_lower for w in ["left lower", "left", "ఎడమ వైపు", "ఎడమ", "बाईं", "बाएं", "बायां"]):
            extracted["location"] = "left"
        elif any(w in t_lower for w in ["center", "middle", "upper", "మధ్య", "పైభాగంలో", "बीच", "ऊपर"]):
            extracted["location"] = "center"

        # 4. Severity Scale (0 to 10)
        sev_match = re.search(r"\b([0-9]|10)\b", t_lower)
        if sev_match and (len(t_lower.split()) <= 3 or "scale" in user_prompt.lower() or "severity" in user_prompt.lower()):
            val = int(sev_match.group(1))
            if 0 <= val <= 10:
                extracted["severity"] = val

        # 5. Vomiting (with Negation!)
        if any(w in t_lower for w in ["no vomiting", "not vomiting", "వాంతులు లేవు", "ఉల్టీ లేదు", "उल्टी नहीं"]):
            extracted["vomiting"] = False
        elif any(w in t_lower for w in ["vomit", "vomited", "vomiting", "వాంతులు", "వాంతి", "ఉల్టీ", "उल्टी"]):
            extracted["vomiting"] = True

        # 6. Breathlessness (with Negation!)
        if any(w in t_lower for w in ["no breathlessness", "ఆయాసం లేదు", "ఊపిరి ఇబ్బంది లేదు", "సాన్స్ లేదు", "सांस की तकलीफ नहीं"]):
            extracted["breathlessness"] = False
        elif any(w in t_lower for w in ["breathlessness", "breathing difficulty", "difficulty breathing", "shortness of breath", "ఆయాసం", "ఊపిరి", "सांस फूल", "सांस लेने में तकलीफ"]):
            extracted["breathlessness"] = True

        # 7. Fever (with Negation!)
        if any(w in t_lower for w in ["no fever", "don't have fever", "do not have fever", "not having fever", "జ్వరం లేదు", "బుఖార్ లేదు", "बुखार नहीं"]):
            extracted["fever"] = False
        elif any(w in t_lower for w in ["have fever", "got fever", "suffering from fever", "జ్వరం ఉంది", "బుఖార్ ఉంది", "बुखार है"]):
            extracted["fever"] = True
        elif t_lower.strip() in ["fever", "జ్వరం", "బుఖార్", "बुखार"]:
            extracted["fever"] = True

        # 8. Sweating
        if any(w in t_lower for w in ["no sweating", "చెమటలు లేవు", "पसीना नहीं"]):
            extracted["sweating"] = False
        elif any(w in t_lower for w in ["sweating", "sweat", "cold sweat", "చెమటలు", "చెమట", "पसीना"]):
            extracted["sweating"] = True

        # 9. Direct touch YES / NO answers
        if t_lower.strip() in ["yes", "true", "అవును", "हाँ", "1"]:
            if "vomit" in user_prompt.lower() or "వాంతులు" in user_prompt.lower() or "उल्टी" in user_prompt.lower():
                extracted["vomiting"] = True
            elif "fever" in user_prompt.lower() or "జ్వరం" in user_prompt.lower() or "बुखार" in user_prompt.lower():
                extracted["fever"] = True
            elif "breath" in user_prompt.lower() or "ఊపిరి" in user_prompt.lower() or "సాన్స్" in user_prompt.lower():
                extracted["breathlessness"] = True
        elif t_lower.strip() in ["no", "false", "లేదు", "नहीं", "0"]:
            if "vomit" in user_prompt.lower() or "వాంతులు" in user_prompt.lower() or "उल्टी" in user_prompt.lower():
                extracted["vomiting"] = False
            elif "fever" in user_prompt.lower() or "జ్వరం" in user_prompt.lower() or "बुखार" in user_prompt.lower():
                extracted["fever"] = False
            elif "breath" in user_prompt.lower() or "ఊపిరి" in user_prompt.lower() or "సాన్స్" in user_prompt.lower():
                extracted["breathlessness"] = False

        return json.dumps(extracted)
