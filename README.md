# SIH26047 — MediKiosk (Part 1: Clinical History & Conversational AI Engine)

A lightweight, deterministic, multilingual clinical-history intake engine for outpatient hospital kiosks.

---

## 🏥 Role & Architecture Boundary

Part 1 is strictly responsible for:
```
PATIENT INPUT (Voice / Text / Touch in English, Telugu, Hindi)
    ↓
ASR Layer (IndicConformer Interface)
    ↓
Clinical Information Extraction (LLM + Strict Pydantic Validation)
    ↓
Deterministic State Machine (Structured Question Engine)
    ↓
Adaptive Follow-Up Questions (Missing Fields Priority)
    ↓
Deterministic Red-Flag Rule Engine (GREEN / YELLOW / RED)
    ↓
Physician-Ready Clinical History JSON Contract (For Part 3 Integration)
```

> **IMPORTANT CLINICAL SAFETY BOUNDARIES:**
> - The system **NEVER diagnoses** the patient.
> - The system **NEVER infers missing medical facts** (unknown fields remain `null`).
> - The system distinguishes explicit **negation** (e.g. `"I don't have fever"` ➔ `fever: false` vs not mentioned ➔ `fever: null`).
> - Triage flags (**RED**, **YELLOW**, **GREEN**) are governed by **deterministic Python rules**, not arbitrary LLM loops.

---

## 🛠️ Technology Stack

- **Frontend**: Streamlit (Elder-friendly, large buttons, high-contrast touch/voice/text UI).
- **Backend API**: Python 3.11 + FastAPI + Uvicorn.
- **Clinical State Engine**: Python + Pydantic v2 + YAML symptom configurations.
- **LLM Layer**: Grok (xAI API) / Groq (Llama-3.3) / Offline Deterministic Fallback.
- **ASR Layer**: IndicConformer ASR interface abstraction.
- **Testing**: pytest + pytest-asyncio (16/16 test cases passing).

---

## 📁 Project Structure

```
hospital/
├── app/
│   ├── main.py                     # FastAPI application entrypoint
│   ├── api/
│   │   └── routes.py               # REST API endpoints
│   ├── core/
│   │   ├── config.py               # Settings & .env loader
│   │   └── logging_config.py       # Centralized logging
│   ├── models/
│   │   ├── patient.py              # Patient session schemas
│   │   ├── question.py             # Question definitions & localized prompts
│   │   ├── history.py              # Official Part 1 Clinical History JSON Contract
│   │   └── triage.py               # Triage flags (GREEN / YELLOW / RED)
│   ├── asr/
│   │   ├── base.py                 # Abstract ASR Provider interface
│   │   └── indic_asr.py            # AI4Bharat IndicConformer implementation
│   ├── llm/
│   │   ├── client.py               # Unified LLM caller (Grok / Groq / Mock)
│   │   ├── prompts.py              # Constrained extraction prompts
│   │   └── extraction.py           # Pydantic extraction & validation pipeline
│   ├── clinical/
│   │   ├── symptom_config.py       # YAML symptom questionnaire loader
│   │   ├── question_engine.py      # Deterministic adaptive question engine
│   │   └── triage_rules.py         # Deterministic red-flag triage rules
│   ├── services/
│   │   └── history_service.py      # Isolated session coordinator
│   └── ui/
│       ├── components.py           # Kiosk UI styling
│       └── streamlit_app.py        # Streamlit touch / voice / text UI
├── config/
│   └── symptoms/
│       ├── chest_pain.yaml         # Chest pain HPI questionnaire
│       ├── fever.yaml              # Fever HPI questionnaire
│       └── general_history.yaml    # Past history, allergies, medications
├── tests/
│   ├── test_api.py                 # API routes & session isolation tests
│   ├── test_extraction.py          # Multilingual & negation extraction tests
│   ├── test_question_engine.py     # Deterministic question engine tests
│   └── test_triage.py              # Red-flag triage safety tests
├── .env.example
├── requirements.txt
├── run.ps1                         # PowerShell launch script
├── run.sh                          # Bash launch script
└── README.md
```

---

## 🚀 Quick Setup & Execution

### 1. Install Dependencies
```bash
cd hospital
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` or use existing keys:
```bash
GROK_API_KEY=your_grok_api_key
GROQ_API_KEY=your_groq_api_key
MOCK_MODE=false
```

### 3. Run Automated Tests
```bash
pytest tests/ -v
```
*(All 16 test cases pass with 100% success rate)*

### 4. Launch Services
**Windows (PowerShell):**
```powershell
.\run.ps1
```
**Linux / macOS:**
```bash
chmod +x run.sh
./run.sh
```

- **Streamlit Kiosk UI**: `http://127.0.0.1:8501`
- **FastAPI Backend Swagger**: `http://127.0.0.1:8001/docs`

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status check |
| `POST` | `/session/start` | Initialize an isolated patient visit session |
| `POST` | `/session/{visit_id}/message` | Submit patient text or touchscreen response |
| `POST` | `/session/{visit_id}/audio` | Submit patient voice recording (.wav / .mp3) |
| `GET` | `/session/{visit_id}/next-question` | Retrieve the next highest-priority missing question |
| `GET` | `/session/{visit_id}/state` | Fetch current structured history state |
| `POST` | `/session/{visit_id}/complete` | Finalize session and evaluate triage |

---

## 📋 Stable Output Contract for Part 3 Integration

```json
{
  "patient_id": "PAT-0001",
  "visit_id": "VIS-0001",
  "language": "te",
  "chief_complaint": {
    "text": "chest pain",
    "canonical": "chest_pain"
  },
  "hpi": {
    "duration_days": 4,
    "location": "left",
    "severity": 7,
    "character": "pressure",
    "radiation": "left arm",
    "aggravating_factors": [],
    "relieving_factors": [],
    "breathlessness": true,
    "sweating": true,
    "nausea": null,
    "dizziness": null,
    "fever": null,
    "cough": null
  },
  "past_history": ["diabetes"],
  "past_surgical_history": [],
  "medications": ["bp_sugar_meds"],
  "allergies": ["none"],
  "family_history": [],
  "personal_history": {},
  "review_of_systems": {},
  "triage": {
    "flag": "RED",
    "priority": true,
    "reason_codes": [
      "CHEST_PAIN_WITH_BREATHLESSNESS",
      "SEVERE_CHEST_PAIN_WITH_AUTONOMIC_FEATURES"
    ],
    "triggering_parameters": {
      "chief_complaint": "chest pain",
      "breathlessness": true,
      "severity": 7,
      "sweating": true,
      "radiation": "left arm"
    },
    "evaluated_at": "2026-08-24T22:49:12.311659",
    "recommendation": "Priority clinical attention required. Alert triage nursing staff immediately."
  },
  "metadata": {
    "completed": true,
    "created_at": "2026-08-24T22:49:12.311659",
    "engine_version": "1.0"
  }
}
```

---

## 🧪 Verified Test Suite (16/16 Passed)

1. `test_extract_english_complaint_and_duration`: Extracts complaint & duration from English text.
2. `test_extract_telugu_response`: Extracts complaint & duration from Telugu text.
3. `test_extract_mixed_code_switching`: Normalizes Telugu-English mixed input.
4. `test_extract_hindi_response`: Extracts complaint & duration from Hindi text.
5. `test_negation_fever_and_breathlessness`: Distinguishes `"I don't have fever"` (`false`) from `"I have fever"` (`true`) and unmentioned (`null`).
6. `test_question_engine_selects_highest_priority_missing_field`: Adaptively selects the next missing question by priority.
7. `test_question_engine_telugu_localization`: Localizes question text and options to Telugu.
8. `test_question_engine_completion_on_all_required_fields`: Completes session when required fields are filled.
9. `test_red_flag_chest_pain_with_breathlessness`: Deterministically triggers **RED** priority on chest pain + breathlessness.
10. `test_red_flag_chest_pain_with_sweating_and_radiation`: Triggers **RED** on severe chest pain + arm radiation + sweating.
11. `test_red_flag_fever_with_respiratory_distress`: Triggers **RED** on fever + breathing difficulty.
12. `test_yellow_flag_severe_pain_alone`: Triggers **YELLOW** on severe pain without autonomic red flags.
13. `test_green_flag_routine_condition`: Triggers **GREEN** for routine mild symptoms.
14. `test_health_endpoint`: Verifies `/health` endpoint.
15. `test_start_session_endpoint`: Verifies session initialization via API.
16. `test_session_isolation_independent_visits`: Verifies complete data isolation between Patient A and Patient B.
