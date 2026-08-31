# SIH26047 — MediKiosk (Part 3)
## Patient Records, Doctor Panel, RAG, Visit History & Integration Layer

Part 3 is the integration and persistent-record layer for **MediKiosk**, consuming structured outputs from Part 1 (Clinical History Engine) and Part 2 (Medical Document Engine) into a unified hospital-style clinical record system.

---

## 🏛️ System Architecture

```
                    STREAMLIT (app.py)
                        │
        ┌───────────────┼────────────────┐
        │               │                │
     PATIENT          DOCTOR         PHARMACIST / STAFF
        │               │                │
        └───────────────┼────────────────┘
                        ↓
                 FASTAPI BACKEND
                        ↓
                  SERVICE LAYER
          (Grok LLM, Vector RAG, ABDM/FHIR)
                        ↓
                 POSTGRESQL DB
          (JSONB flexible fields + pgvector)
```

---

## 🔑 Key Features & Design Rules

1. **Primary Database**: PostgreSQL with relational tables (`patients`, `visits`, `clinical_histories`, `documents`, `prescriptions`, `prescription_items`, `users`, `doctors`, `pharmacists`, `audit_logs`, `embeddings`) and `JSONB` for flexible medical report structures.
2. **Stable Patient & Visit Identifiers**: Standardized IDs (`PAT-000001`, `VIS-000001`, `DOC-000001`, `RX-000001`). Repeat visits create new visit records without overwriting historical consultation data.
3. **Patient Data Isolation**: Strict backend enforcement scoping all queries by `patient_id` (`WHERE patient_id = :current_patient_id`). Vector retrieval is bounded to the authenticated patient's records.
4. **Grok LLM Summarization**: Generates non-diagnostic, grounded doctor briefs based strictly on supplied history and lab reports.
5. **Doctor Voice Prescriptions**: Speech-to-text dictation parsing into structured JSON with MANDATORY physician review before final confirmation and PDF generation.
6. **Pharmacist Verification**: Dedicated review workflow for OCR/handwritten prescription extractions before final status confirmation.
7. **ABDM & FHIR Interoperability**: Mock ABDM adapter and FHIR R4 resource converters (`Patient`, `Encounter`, `DiagnosticReport`, `MedicationRequest`).

---

## 🛠️ Technology Stack

- **Frontend**: Streamlit
- **Backend**: FastAPI
- **Database**: PostgreSQL (JSONB + `pgvector`)
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Embeddings**: SentenceTransformers (`BAAI/bge-small-en-v1.5`)
- **LLM**: Grok API / Groq
- **PDF Generation**: ReportLab
- **Containerization**: Docker Compose

---

## 🚀 Quick Start (Local & Docker)

### 1. Running with Docker Compose

```bash
docker compose up --build
```
- **Backend API**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Streamlit Frontend**: `http://localhost:8501`

### 2. Manual Development Setup

#### Start PostgreSQL (with pgvector)
```bash
docker run -d --name medikiosk-pg -e POSTGRES_DB=medikiosk -e POSTGRES_USER=medikiosk -e POSTGRES_PASSWORD=medikiosk -p 5433:5432 pgvector/pgvector:pg15
```

#### Run Backend
```bash
pip install -r backend/requirements.txt
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Run Frontend
```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```

---

## 🧪 Running Integration Tests

Execute the complete pytest suite:
```bash
pytest backend/tests -v
```

All 4 core integration test suites cover:
- Patient creation & repeat visit preservation (`test_patients_visits.py`)
- Doctor voice prescription dictation, review, & PDF generation (`test_prescriptions.py`)
- Strict patient data isolation in RAG retrieval (`test_rag_isolation.py`)
- ABDM mock records & FHIR JSON export (`test_abdm_fhir.py`)

---

## 🔐 Default Demo Accounts

| Role | Username | Password |
|---|---|---|
| **Doctor** | `doctor1` | `doctor123` |
| **Patient** | `patient1` | `patient123` |
| **Pharmacist** | `pharm1` | `pharm123` |
| **Staff** | `staff1` | `staff123` |
