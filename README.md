# SIH26047 — MediKiosk: Integrated Clinical Intake & Hospital Management System

MediKiosk is an intelligent, multi-role hospital intake and clinical decision support system designed to streamline patient registration, multilingual AI intake, document OCR extraction, doctor consultation, and prescription verification.

---

## 🌟 Key Features

- **Multilingual Patient Intake (Part 1)**: Interactive symptom capture supporting English, Telugu, and Hindi with red flag triage evaluation.
- **Smart Document Processing & OCR (Part 2)**: OCR pipeline extracting structured parameters from lab reports (CBC, LFT, etc.), radiographs, and handwritten prescriptions with automated abnormal range detection.
- **Doctor Consultation & AI Briefings (Part 3)**: Comprehensive doctor review panel with Groq AI clinical summaries, history review, diagnosis logging, and digital PDF prescription generation.
- **Pharmacist Verification Queue**: Role-based verification workflow for OCR extracted prescriptions.
- **Unified Streamlit Interface**: Intuitive, role-based dashboard for Patients, Doctors, Pharmacists, and Staff.
- **PostgreSQL + pgvector Integration**: Scalable relational & vector database storage with ABHA/FHIR health record compliance.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- PostgreSQL database (or Docker for containerized setup)
- Groq API Key (for LLM clinical summaries & extraction)

### 2. Environment Setup
Copy the example environment file and set your API keys:
```bash
cp .env.example .env
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Running MediKiosk

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
- **Terminal 1 (FastAPI Backend):**
  ```bash
  python server.py
  ```
- **Terminal 2 (Streamlit UI):**
  ```bash
  streamlit run app.py
  ```

---

## 🔑 Demo Access Credentials

| Role | Username | Password | Notes |
|---|---|---|---|
| **Patient** | `patient1` | `patient123` | Patient ID: `PAT-000001` (Rajesh Kumar) |
| **Doctor** | `doctor1` | `doctor123` | Doctor ID: `DOC-101` (Dr. A. Sharma) |
| **Pharmacist** | `pharm1` | `pharm123` | Pharmacist ID: `PHARM-101` |
| **Staff** | `staff1` | `staff123` | Front-desk Reception |

---

## 📁 Project Architecture

```
├── app.py                      # Main Unified Streamlit Frontend
├── server.py                   # FastAPI Backend Server Launcher
├── database/                   # Database models & connection managers
├── part1/                      # Multilingual Clinical Intake & Triage
├── part2/                      # OCR, Extraction & Document Intelligence
├── part3/                      # Unified Backend, Doctor Panel & Prescriptions
├── scripts/                    # Database migrations & utility scripts
├── run_medikiosk.ps1           # Windows launch script
├── run_medikiosk.sh            # Linux/macOS launch script
├── requirements.txt            # Python dependencies
└── docker-compose.yml          # PostgreSQL + pgvector configuration
```

---

## 🧪 Testing

```powershell
# Part 1 Tests
$env:PYTHONPATH="part1"; pytest part1/tests -v

# Part 2 Tests
$env:PYTHONPATH="part2/backend"; pytest part2/backend/tests -v
```
