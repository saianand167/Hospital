# MediKiosk — Part 2: Medical Document Digitization & Structured Extraction

This module is a core component of the **MediKiosk Smart India Hackathon (SIH26047)** platform. It is a practical, lightweight, and demonstrative prototype of the **AI-powered medical document digitization and intelligence pipeline**.

It handles the ingestion of diverse medical documents (handwritten/printed prescriptions, lab reports, discharge summaries, imaging reports, consultation notes), applies pre-processing, performs multilingual OCR, classifies the document, extracts key clinical structured entities using Groq LLM, evaluates confidence, and presents an interactive human-in-the-loop verification desk.

---

## 📂 1. Project Structure

```
part2-document-intelligence/
├── .env                  # Configuration variables
├── .env.example          # Template environment config
├── requirements.txt      # Streamlit/UI frontend requirements
├── README.md             # Integration & setup documentation
├── frontend/
│   └── app.py            # Streamlit interactive UI application
└── backend/
    ├── requirements.txt  # FastAPI backend dependencies
    ├── tests/
    │   ├── test_pipeline.py  # pytest suite covering 20 spec cases
    │   └── fixtures/     # Synthetic medical fixtures
    └── app/
        ├── __init__.py
        ├── main.py       # FastAPI application entrypoint (in-memory store)
        ├── config.py     # Configuration management via pydantic-settings
        ├── api/
        │   ├── __init__.py
        │   └── documents.py  # Document processing and verification routes
        ├── schemas/
        │   ├── __init__.py
        │   └── documents.py  # Core Pydantic data schemas & contract
        ├── utils/
        │   ├── __init__.py
        │   └── security.py   # File extension & safety validations
        ├── services/
        │   ├── __init__.py
        │   ├── ocr.py           # OCR interface (Tesseract / Mock)
        │   ├── preprocessing.py # PIL/OpenCV image enhancements
        │   └── pdf_processor.py # PyMuPDF text & scan pdf processing
        └── agents/
            ├── __init__.py
            ├── classifier_agent.py  # Fast rule-based + LLM classifier
            ├── extraction_agent.py  # Type-specific clinical extraction agent
            └── validation_agent.py  # Deterministic range check & validation agent
```

---

## 🚀 2. Setup Commands

### Setup and Start FastAPI Backend
```bash
cd part2-document-intelligence/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Setup and Start Streamlit Frontend
In a new terminal:
```bash
cd part2-document-intelligence
pip install -r requirements.txt
streamlit run frontend/app.py
```

---

## ⚙️ 3. Environment Variables (`.env.example`)

```env
# Groq API Configuration (required if LLM_PROVIDER=groq and MOCK_MODE=false)
GROQ_API_KEY=

# Pluggable Provider Selection: "mock" (zero-setup) or "groq" / "tesseract"
LLM_PROVIDER=mock
OCR_PROVIDER=mock

# Mock mode: set to false to connect to active APIs/Tesseract local engine
MOCK_MODE=true

# OCR confidence threshold below which document goes to verification (0.0 to 1.0)
OCR_CONFIDENCE_THRESHOLD=0.75

# Port configuration
PORT=8000

# Temp folder storage path
STORAGE_DIR=./temp_uploads
```

---

## 📖 4. API Endpoints

- **`GET /health`**: Monitoring health check.
- **`POST /documents/upload`**: Ingest file, process pipeline, and return `StructuredDocument`.
- **`POST /documents/process`**: Alias for upload.
- **`GET /documents/{document_id}`**: Get full in-memory document state.
- **`GET /documents/{document_id}/raw-text`**: Get raw OCR text page-by-page.
- **`GET /documents/{document_id}/structured`**: Get only document type and flexible clinical data.
- **`POST /documents/{document_id}/verify`**: Submit corrected verification payload.

---

## 📝 5. Sample JSON Contract (Output Schema)

Below is an example output payload for a processed `LAB_REPORT`:

```json
{
  "document_id": "DOC-7BD42E",
  "document_type": "LAB_REPORT",
  "metadata": {
    "document_date": "2026-08-20",
    "source": "patient_upload",
    "hospital_name": "Apollo Labs",
    "doctor_name": "Dr. Ramesh Sharma",
    "language": "eng"
  },
  "ocr": {
    "raw_text": "Apollo Labs\nHemoglobin: 11.5 g/dL (Ref: 12.0 - 16.0)\nWBC: 12500 /uL (Ref: 4000 - 11000)\nPlatelets: 250000 /uL (Ref: 150000 - 450000)",
    "pages": [
      {
        "page": 1,
        "text": "Apollo Labs\nHemoglobin: 11.5 g/dL (Ref: 12.0 - 16.0)\nWBC: 12500 /uL (Ref: 4000 - 11000)\nPlatelets: 250000 /uL (Ref: 150000 - 450000)"
      }
    ],
    "language": "eng"
  },
  "classification": {
    "document_type": "LAB_REPORT",
    "confidence": 0.95
  },
  "extraction": {
    "status": "success",
    "confidence": 0.85
  },
  "confidence": {
    "ocr": 0.85,
    "classification": 0.95,
    "extraction": 0.85
  },
  "data": {
    "tests": [
      {
        "name": "Hemoglobin",
        "value": 11.5,
        "unit": "g/dL",
        "reference_range": "12.0 - 16.0",
        "abnormal": true
      },
      {
        "name": "WBC",
        "value": 12500,
        "unit": "/uL",
        "reference_range": "4000 - 11000",
        "abnormal": true
      },
      {
        "name": "Platelets",
        "value": 250000,
        "unit": "/uL",
        "reference_range": "150000 - 450000",
        "abnormal": false
      }
    ]
  },
  "verification": {
    "required": false,
    "verified": false,
    "verified_by": null,
    "corrected_data": null
  },
  "upload_timestamp": "2026-08-24T16:00:55.123456",
  "file_name": "lab_report.png"
}
```

---

## 🛠️ 6. Part 2 → Part 3 Integration Contract

Part 2 runs completely stateless (in-memory storage for demonstration). The stable contract interface between Part 2 and Part 3 is the Pydantic schema **`StructuredDocument`**.

Part 3 consumed output is:
```json
{
  "document_id": "...",
  "document_type": "...",
  "metadata": {
    "document_date": "YYYY-MM-DD",
    "source": "patient_upload"
  },
  "raw_text": "...",
  "structured_data": {}, 
  "confidence": {},
  "verification_required": false,
  "verified": false
}
```
Part 3 is responsible for persistent storage in PostgreSQL database using a JSONB column to map `StructuredDocument.data` dynamically without DB schema changes.

---

## ⚠️ 7. Prototype Limitations

1. **No Database Persistence**: Uses an in-memory session dictionary. Restarting the server clears all uploaded document results.
2. **Mock Mode Fallback**: When `MOCK_MODE=true`, OCR output and extraction fields are deterministic synthetic payloads to avoid API latency and keys dependency.
3. **Indic OCR Support**: Basic multi-language flags (`tel`, `hin`) map to Tesseract language packs, but complex Indian-language handwritings require external API endpoints (e.g. Bhashini) to achieve high accuracy.
4. **No Medical Inference**: The validation layer compares tests to reference ranges but does NOT suggest diagnoses.
