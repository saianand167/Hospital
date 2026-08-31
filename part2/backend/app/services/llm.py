"""
LLM Provider Abstraction.
Supports Groq API and a local Mock LLM Provider.
"""
from abc import ABC, abstractmethod
from typing import Type, Dict, Any, Optional
from pydantic import BaseModel
import httpx
import json
import re
import time
from app.config import settings

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text output from the LLM."""
        pass

    @abstractmethod
    def generate_json(self, prompt: str, schema: Type[BaseModel]) -> Dict[str, Any]:
        """
        Generate structured output from the LLM conforming to the Pydantic schema.
        Returns a dictionary representing the schema.
        """
        pass

class GroqLLMProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        # mixtral-8x7b-32768 was deprecated — using openai/gpt-oss-120b
        self.model = "openai/gpt-oss-120b"

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0
        }

        # Handle retries for rate limits or transient errors
        for attempt in range(3):
            try:
                with httpx.Client(timeout=30.0) as client:
                    res = client.post(self.url, headers=headers, json=payload)
                    if res.status_code == 429: # Rate limit
                        time.sleep(2 ** attempt)
                        continue
                    res.raise_for_status()
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Groq API failure: {str(e)}")
                time.sleep(1)
        return ""

    def generate_json(self, prompt: str, schema: Type[BaseModel]) -> Dict[str, Any]:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        system_instruction = (
            "You are a medical data extraction system. "
            "Extract structured clinical entities from the OCR text of a medical document. "
            "Extract ONLY information explicitly present in the document. Never diagnose diseases, recommend treatments, or invent details. "
            "If a value is not mentioned, set it to null. "
            "You must return ONLY a valid JSON object matching this schema:\n"
            f"{schema_json}\n\n"
            "Do not wrap the JSON in ```json markdown formatting. Return the raw JSON string directly."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        }

        for attempt in range(3):
            try:
                with httpx.Client(timeout=30.0) as client:
                    res = client.post(self.url, headers=headers, json=payload)
                    if res.status_code == 429:
                        time.sleep(2 ** attempt)
                        continue
                    res.raise_for_status()
                    text_response = res.json()["choices"][0]["message"]["content"]
                    
                    # Clean response if LLM added markdown formatting
                    text_response = text_response.strip()
                    if text_response.startswith("```json"):
                        text_response = text_response[7:]
                    if text_response.endswith("```"):
                        text_response = text_response[:-3]
                    
                    return json.loads(text_response.strip())
            except Exception as e:
                if attempt == 2:
                    print(f"Groq structured extraction failed: {e}")
                    return {}
                time.sleep(1)
        return {}

class MockLLMProvider(LLMProvider):
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if "classify" in prompt.lower() or (system_prompt and "classifier" in system_prompt.lower()):
            return "LAB_REPORT"
        return "Mock response"

    def generate_json(self, prompt: str, schema: Type[BaseModel]) -> Dict[str, Any]:
        # Return structured mock data based on the schema name
        schema_name = schema.__name__.lower()
        if "prescription" in schema_name or "medication" in schema_name:
            return {
                "medications": [
                    {
                        "name": "Metformin 500mg",
                        "dose": "1 tablet",
                        "route": "oral",
                        "frequency": "BD",
                        "duration": "5 days",
                        "instructions": "After meals",
                        "confidence": 0.95,
                        "needs_verification": False
                    },
                    {
                        "name": "Amlodpn 5mg", # Intentional spelling error to test pharmacist review
                        "dose": "1 tablet",
                        "route": "oral",
                        "frequency": "OD",
                        "duration": "10 days",
                        "instructions": "Morning",
                        "confidence": 0.60, # Low confidence -> needs verification
                        "needs_verification": True
                    }
                ]
            }
        elif "lab" in schema_name or "test" in schema_name:
            return {
                "tests": [
                    {
                        "name": "Hemoglobin",
                        "value": 11.5,
                        "unit": "g/dL",
                        "reference_range": "12.0 - 16.0",
                        "abnormal": True
                    },
                    {
                        "name": "WBC",
                        "value": 12500,
                        "unit": "/uL",
                        "reference_range": "4000 - 11000",
                        "abnormal": True
                    },
                    {
                        "name": "Platelets",
                        "value": 250000,
                        "unit": "/uL",
                        "reference_range": "150000 - 450000",
                        "abnormal": False
                    }
                ]
            }
        elif "discharge" in schema_name:
            return {
                "hospital": "City General Hospital",
                "admission_date": "2026-08-10",
                "discharge_date": "2026-08-15",
                "diagnosis": ["Acute Appendicitis", "Hypertension"],
                "procedures": ["Laparoscopic Appendectomy"],
                "medications": ["Amoxicillin 500mg TDS for 5 days", "Amlodipine 5mg OD for 30 days"],
                "investigations": "Ultrasound abdomen confirmed appendicitis",
                "follow_up": "After 1 week in OPD",
                "doctor": "Dr. Ramesh Sharma"
            }
        elif "imaging" in schema_name:
            return {
                "modality": "X-ray",
                "body_part": "Chest",
                "findings": "Normal cardiac silhouette. No focal lung consolidation, pleural effusion, or pneumothorax.",
                "impression": "No active cardiopulmonary disease."
            }
        
        # Generic fallback
        return {}

def get_llm_provider(provider_name: str) -> LLMProvider:
    if provider_name.lower() == "groq" and settings.groq_api_key:
        return GroqLLMProvider(api_key=settings.groq_api_key)
    return MockLLMProvider()
