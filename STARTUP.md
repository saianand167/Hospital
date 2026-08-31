# SIH26047 — MediKiosk Startup & Integration Guide

## 1. Quick Start Guide

### Step 1: Start PostgreSQL + pgvector via Docker
```bash
docker compose up -d
```
To verify the container is running and healthy:
```bash
docker compose ps
```

### Step 2: Configure Environment (if not already present)
Copy `.env.example` to `.env` and configure your API keys:
```bash
cp .env.example .env
```
*(Ensure `GROQ_API_KEY` is provided for AI summarization & extraction).*

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Launch MediKiosk
**Windows (PowerShell):**
```powershell
.\run_medikiosk.ps1
```

**Linux / macOS:**
```bash
chmod +x run_medikiosk.sh
./run_medikiosk.sh
```

**Manual Launch (Two Terminals):**
- Terminal 1 (Backend):
  ```bash
  uvicorn app.main:app --app-dir part3/backend --host 0.0.0.0 --port 8000 --reload
  ```
- Terminal 2 (Unified Streamlit UI):
  ```bash
  streamlit run app.py
  ```

---

## 2. Architecture & Role Access

### Pre-Seeded Demo Accounts
| Role | Username | Password | Notes |
|---|---|---|---|
| **Patient** | `patient1` | `patient123` | Patient ID: `PAT-000001` (Rajesh Kumar) |
| **Doctor** | `doctor1` | `doctor123` | Doctor ID: `DOC-101` (Dr. A. Sharma) |
| **Pharmacist** | `pharm1` | `pharm123` | Pharmacist ID: `PHARM-101` |
| **Staff** | `staff1` | `staff123` | Front-desk staff |

### Patient Self-Registration
New patients can click the **"📝 Register New Patient"** tab on the home screen. A new sequential `PAT-XXXXXX` ID is generated automatically, and they are logged in directly.

---

## 3. End-to-End Workflow

1. **Patient Intake**:
   - Register or login as `patient1`.
   - Go to **"🩺 Clinical Intake & Symptoms"** -> Start a new visit.
   - Speak or type chief complaint and symptoms (English, Telugu, Hindi).
   - System evaluates red flags & saves structured clinical history to PostgreSQL.

2. **Document OCR Intelligence**:
   - Go to **"📑 Medical Document Upload"**.
   - Upload any lab report (CBC, LFT), radiograph, or handwritten prescription.
   - System extracts parameters into PostgreSQL `JSONB` and detects any abnormal ranges.

3. **Doctor Review & Prescription**:
   - Switch role to `doctor1`.
   - Open patient from the queue or search by Patient ID.
   - View Groq AI Doctor Briefing summary, previous visits, and uploaded reports.
   - Dictate or type a prescription -> Doctor reviews and confirms.
   - Generates an official signed PDF prescription stored in PostgreSQL.

4. **Pharmacist Verification**:
   - Switch role to `pharm1`.
   - View any pending handwritten prescriptions marked `verification_required = true`.
   - Review original scan alongside OCR candidates, correct if needed, and verify.

---

## 4. Running Unit Tests

**Part 1 Tests (30/30 Tests):**
```powershell
$env:PYTHONPATH="part1"; pytest part1/tests -v
```

**Part 2 Tests (14/14 Tests):**
```powershell
$env:PYTHONPATH="part2/backend"; pytest part2/backend/tests -v
```

**Database Migration from SQLite (Optional):**
```bash
python scripts/migrate_sqlite_to_postgres.py
```
