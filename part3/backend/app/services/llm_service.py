import requests
import json
import logging
from typing import Dict, Any, List
from app.config import settings

logger = logging.getLogger(__name__)

class GrokLLMService:
    def __init__(self):
        # Settings are read fresh from os.environ; no caching
        pass

    @property
    def api_key(self):
        return settings.GROK_API_KEY

    @property
    def api_base(self):
        return settings.GROK_API_BASE.rstrip('/')

    @property
    def model(self):
        return settings.GROK_MODEL

    def _call_groq_api(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        if not self.api_key or self.api_key in ("mock-grok-key", ""):
            raise ValueError("No valid Groq API key configured. Set GROQ_API_KEY in your .env file.")

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1200
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            return res_json["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Groq API error {response.status_code}: {response.text}")
            raise Exception(f"Groq API returned status {response.status_code}: {response.text[:200]}")

    def generate_doctor_summary(
        self,
        current_history: Dict[str, Any],
        previous_visits: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
        triage_flag: str
    ) -> Dict[str, Any]:
        """
        Generate structured doctor summary. Strict non-diagnostic requirement.
        """
        prompt = f"""You are a clinical summarization assistant preparing a patient brief for a doctor.
CRITICAL RULES:
1. Use ONLY the provided records. Do not invent missing information.
2. DO NOT DIAGNOSE or infer clinical conclusions. State only reported symptoms, documented history, and findings.
3. Keep it concise, structured, and clear.

PATIENT RECORDS:
- Triage Priority: {triage_flag}
- Current Clinical History: {json.dumps(current_history, indent=2)}
- Previous Visits: {json.dumps(previous_visits, indent=2)}
- Medical Documents/Labs: {json.dumps(documents, indent=2)}

Respond with JSON adhering strictly to this format:
{{
  "chief_complaint": "Summary of chief complaint",
  "hpi": "Summary of history of present illness",
  "relevant_past_history": "Summary of past history",
  "medications": ["Medication 1", "Medication 2"],
  "allergies": ["Allergy 1"],
  "family_personal_history": "Summary of family and personal history",
  "relevant_previous_investigations": "Key findings from previous lab reports/imaging",
  "previous_treatments": "Previous medications or treatments",
  "current_triage_flag": "{triage_flag}"
}}
"""
        messages = [
            {"role": "system", "content": "You are a clinical record summarizer for physicians. You return structured valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            raw_text = self._call_groq_api(messages)
            # Find JSON block
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start != -1 and json_end != -1:
                parsed = json.loads(raw_text[json_start:json_end])
                return parsed
        except Exception as e:
            logger.warning(f"Grok API summary call failed or unconfigured ({str(e)}). Using deterministic summary fallback.")

        # Fallback deterministic summary builder
        cc = current_history.get("chief_complaint", {})
        if isinstance(cc, dict):
            cc_str = f"{cc.get('complaint', 'Reported symptoms')} (Duration: {cc.get('duration', 'N/A')}, Severity: {cc.get('severity', 'N/A')})"
        else:
            cc_str = str(cc) if cc else "Patient reported symptoms"

        hpi_data = current_history.get("hpi", {})
        hpi_str = f"Severity: {hpi_data.get('severity', 'N/A')}. Radiation: {hpi_data.get('radiation', 'None')}. Character: {hpi_data.get('character', 'N/A')}." if isinstance(hpi_data, dict) else str(hpi_data)

        past_h = current_history.get("past_history", {})
        past_str = json.dumps(past_h) if isinstance(past_h, dict) else str(past_h)

        meds = current_history.get("medications", [])
        allergies = current_history.get("allergies", [])
        fam = current_history.get("family_history", {})

        doc_summary_items = []
        for doc in documents:
            doc_type = doc.get("document_type", "Document")
            doc_date = doc.get("document_date", "")
            raw = doc.get("raw_text", "")
            doc_summary_items.append(f"{doc_type} ({doc_date[:10] if doc_date else 'N/A'}): {raw[:150]}")

        prev_treat = []
        for pv in previous_visits:
            rx = pv.get("prescription", {})
            if rx and "items" in rx:
                for item in rx["items"]:
                    prev_treat.append(f"{item.get('medicine_name')} {item.get('dose')} {item.get('frequency')}")

        return {
            "chief_complaint": cc_str,
            "hpi": hpi_str,
            "relevant_past_history": past_str if past_str != "{}" else "No significant past history recorded.",
            "medications": meds if isinstance(meds, list) else [str(meds)],
            "allergies": allergies if isinstance(allergies, list) else [str(allergies)],
            "family_personal_history": json.dumps(fam) if isinstance(fam, dict) else str(fam),
            "relevant_previous_investigations": "\n".join(doc_summary_items) if doc_summary_items else "No previous investigations on file.",
            "previous_treatments": ", ".join(prev_treat) if prev_treat else "None documented.",
            "current_triage_flag": triage_flag
        }

    def rag_answer_query(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Answer doctor's query based strictly on retrieved patient records.
        """
        if not retrieved_chunks:
            return {
                "answer": "No relevant patient records found for the specified query.",
                "grounded": True,
                "sources": []
            }

        context_str = ""
        sources = []
        for idx, chunk in enumerate(retrieved_chunks, 1):
            source_id = chunk.get("source_id", f"SRC-{idx}")
            source_type = chunk.get("source_type", "Record")
            doc_date = str(chunk.get("document_date", "N/A"))
            text = chunk.get("content", "")
            context_str += f"\n--- SOURCE [{source_id}] ({source_type}, Date: {doc_date}) ---\n{text}\n"
            sources.append({
                "source_id": source_id,
                "source_type": source_type,
                "document_date": doc_date,
                "snippet": text[:150] + "..." if len(text) > 150 else text
            })

        prompt = f"""You are summarizing medical records for a physician in response to a specific question.
CRITICAL MANDATE:
- Use ONLY the supplied patient records below.
- Do NOT diagnose or invent facts.
- If the answer is not present in the supplied records, explicitly state: "Information not available in patient records."
- Cite the source document/visit ID when useful.

DOCTOR QUERY: {query}

SUPPLIED PATIENT RECORDS:
{context_str}

ANSWER:"""

        messages = [
            {"role": "system", "content": "You are a precise medical retrieval AI assistant. State facts directly from context."},
            {"role": "user", "content": prompt}
        ]

        try:
            answer = self._call_groq_api(messages)
            return {
                "answer": answer,
                "grounded": True,
                "sources": sources
            }
        except Exception as e:
            logger.warning(f"Grok RAG query call failed or unconfigured ({str(e)}). Using deterministic grounding search.")

        # Fallback grounded answer builder
        matches = []
        for chunk in retrieved_chunks:
            content = chunk.get("content", "")
            if any(term in content.lower() for term in query.lower().split()):
                matches.append(f"From {chunk.get('source_type')} ({chunk.get('source_id')}): {content}")

        if matches:
            ans = "\n\n".join(matches)
        else:
            ans = f"Based on the patient's records ({len(retrieved_chunks)} items searched), no specific entry directly addresses: '{query}'."

        return {
            "answer": ans,
            "grounded": True,
            "sources": sources
        }

grok_service = GrokLLMService()
