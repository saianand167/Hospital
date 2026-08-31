import json
import re
from typing import Optional
from app.llm.client import LLMClient
from app.llm.prompts import EXTRACTION_SYSTEM_PROMPT, build_history_aware_prompt
from app.models.history import ClinicalHistoryJSON, HPIState, ChiefComplaint
from app.core.logging_config import logger

class ClinicalExtractor:
    @classmethod
    async def extract_and_update(
        cls,
        patient_text: str,
        history: ClinicalHistoryJSON,
        target_field: Optional[str] = None,
        history_context_str: str = ""
    ) -> ClinicalHistoryJSON:
        """
        Runs LLM extraction with full history-aware retrieval context.
        """
        user_prompt = build_history_aware_prompt(
            patient_text=patient_text,
            target_field=target_field,
            history_context_str=history_context_str
        )
        
        response_text = await LLMClient.generate_completion(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )

        if not response_text:
            return history

        try:
            # Clean possible markdown or reasoning wrappers
            clean_json_str = response_text.strip()
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_json_str)
            if match:
                clean_json_str = match.group(1).strip()
            
            brace_match = re.search(r"(\{[\s\S]*\})", clean_json_str)
            if brace_match:
                clean_json_str = brace_match.group(1)

            data = json.loads(clean_json_str)
            cls._apply_extracted_data(history, data)
        except Exception as e:
            logger.error(f"Failed to parse LLM extraction JSON: {e}, Raw: {response_text}")

        return history

    @classmethod
    def _apply_extracted_data(cls, history: ClinicalHistoryJSON, data: dict):
        # 1. Chief complaint
        cc = data.get("chief_complaint")
        if cc and not history.chief_complaint.text:
            cc_clean = str(cc).strip().lower()
            history.chief_complaint = ChiefComplaint(
                text=cc_clean,
                canonical=cc_clean
            )


        # 2. HPI Fields
        hpi_dict = history.hpi.model_dump()
        for field in [
            "duration_days", "location", "severity", "character", "radiation",
            "breathlessness", "sweating", "dizziness", "vomiting", "fever", "cough"
        ]:
            if field in data and data[field] is not None:
                val = data[field]
                if field == "location" and isinstance(val, str):
                    v_low = val.lower()
                    if "left" in v_low:
                        val = "left"
                    elif "right" in v_low:
                        val = "right"
                    elif "center" in v_low or "middle" in v_low:
                        val = "center"
                hpi_dict[field] = val

        history.hpi = HPIState(**hpi_dict)


        # 3. Lists
        for k in ["past_history", "medications", "allergies"]:
            vals = data.get(k, [])
            if vals and isinstance(vals, list):
                existing = getattr(history, k, [])
                for v in vals:
                    if v and v not in existing:
                        existing.append(v)
                setattr(history, k, existing)
