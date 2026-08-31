-- SIH26047 MediKiosk — PostgreSQL Initialization Script
-- This runs ONCE when the Docker container is first created.
-- It is SAFE to re-run: all statements use IF NOT EXISTS / CREATE OR REPLACE.
-- NEVER add DROP or TRUNCATE commands here.

-- ── Enable pgvector extension ─────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Core Tables ───────────────────────────────────────────────────────────────

-- 1. Doctors (must exist before users foreign key)
CREATE TABLE IF NOT EXISTS doctors (
    id          SERIAL PRIMARY KEY,
    doctor_id   VARCHAR(50) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    department  VARCHAR(100) NOT NULL DEFAULT 'General Medicine',
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 2. Pharmacists
CREATE TABLE IF NOT EXISTS pharmacists (
    id              SERIAL PRIMARY KEY,
    pharmacist_id   VARCHAR(50) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 3. Patients
CREATE TABLE IF NOT EXISTS patients (
    id                  SERIAL PRIMARY KEY,
    patient_id          VARCHAR(50) UNIQUE NOT NULL,  -- e.g. PAT-000001
    name                VARCHAR(100) NOT NULL,
    date_of_birth       VARCHAR(20),
    gender              VARCHAR(20),
    phone               VARCHAR(20),
    email               VARCHAR(100),
    preferred_language  VARCHAR(50) DEFAULT 'English',
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- 4. Users (auth table — links to patients / doctors / pharmacists)
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL,            -- PATIENT, DOCTOR, PHARMACIST, STAFF
    patient_id      VARCHAR(50) REFERENCES patients(patient_id) ON DELETE SET NULL,
    doctor_id       VARCHAR(50) REFERENCES doctors(doctor_id) ON DELETE SET NULL,
    pharmacist_id   VARCHAR(50) REFERENCES pharmacists(pharmacist_id) ON DELETE SET NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 5. Visits
CREATE TABLE IF NOT EXISTS visits (
    id          SERIAL PRIMARY KEY,
    visit_id    VARCHAR(50) UNIQUE NOT NULL,         -- e.g. VIS-000001
    patient_id  VARCHAR(50) NOT NULL REFERENCES patients(patient_id),
    doctor_id   VARCHAR(50) REFERENCES doctors(doctor_id),
    department  VARCHAR(100) DEFAULT 'General Medicine',
    visit_date  TIMESTAMP DEFAULT NOW(),
    status      VARCHAR(20) DEFAULT 'WAITING',       -- WAITING, IN_PROGRESS, COMPLETED
    priority    VARCHAR(20) DEFAULT 'NORMAL',        -- NORMAL, HIGH, EMERGENCY
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 6. Clinical Histories (Part 1 output — one per visit)
CREATE TABLE IF NOT EXISTS clinical_histories (
    id           SERIAL PRIMARY KEY,
    visit_id     VARCHAR(50) UNIQUE NOT NULL REFERENCES visits(visit_id),
    patient_id   VARCHAR(50) NOT NULL REFERENCES patients(patient_id),
    history_json JSONB NOT NULL DEFAULT '{}',
    source       VARCHAR(50) DEFAULT 'Part1_Engine',
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

-- 7. Documents (Part 2 output — uploaded medical files)
CREATE TABLE IF NOT EXISTS documents (
    id                    SERIAL PRIMARY KEY,
    document_id           VARCHAR(50) UNIQUE NOT NULL,  -- e.g. DOC-000001
    patient_id            VARCHAR(50) NOT NULL REFERENCES patients(patient_id),
    visit_id              VARCHAR(50) REFERENCES visits(visit_id),
    document_type         VARCHAR(50) NOT NULL,         -- LAB_REPORT, XRAY, PRESCRIPTION, etc.
    document_date         TIMESTAMP DEFAULT NOW(),
    raw_text              TEXT,
    structured_data       JSONB DEFAULT '{}',
    ocr_confidence        FLOAT DEFAULT 1.0,
    extraction_confidence FLOAT DEFAULT 1.0,
    verification_required BOOLEAN DEFAULT FALSE,
    verified              BOOLEAN DEFAULT TRUE,
    file_reference        VARCHAR(500),
    created_at            TIMESTAMP DEFAULT NOW()
);

-- 8. Prescriptions
CREATE TABLE IF NOT EXISTS prescriptions (
    id              SERIAL PRIMARY KEY,
    prescription_id VARCHAR(50) UNIQUE NOT NULL,        -- e.g. RX-000001
    patient_id      VARCHAR(50) NOT NULL REFERENCES patients(patient_id),
    visit_id        VARCHAR(50) NOT NULL REFERENCES visits(visit_id),
    doctor_id       VARCHAR(50) NOT NULL REFERENCES doctors(doctor_id),
    status          VARCHAR(20) DEFAULT 'DRAFT',        -- DRAFT, FINAL, CANCELLED
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 9. Prescription Items
CREATE TABLE IF NOT EXISTS prescription_items (
    id              SERIAL PRIMARY KEY,
    prescription_id VARCHAR(50) NOT NULL REFERENCES prescriptions(prescription_id) ON DELETE CASCADE,
    medicine_name   VARCHAR(100) NOT NULL,
    dose            VARCHAR(50) NOT NULL,
    route           VARCHAR(50) DEFAULT 'Oral',
    frequency       VARCHAR(50) NOT NULL,
    duration        VARCHAR(50) NOT NULL,
    instructions    VARCHAR(255) DEFAULT 'After food'
);

-- 10. Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id        SERIAL PRIMARY KEY,
    user_id   VARCHAR(50) NOT NULL,
    action    VARCHAR(100) NOT NULL,
    target_id VARCHAR(50),
    details   JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- 11. Embeddings (pgvector — for RAG semantic search on documents)
CREATE TABLE IF NOT EXISTS embeddings (
    id          SERIAL PRIMARY KEY,
    patient_id  VARCHAR(50) NOT NULL REFERENCES patients(patient_id),
    visit_id    VARCHAR(50) REFERENCES visits(visit_id),
    document_id VARCHAR(50) REFERENCES documents(document_id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,   -- CLINICAL_HISTORY, DOCUMENT, DOCTOR_NOTE
    content     TEXT NOT NULL,
    embedding   vector(384),            -- 384-dim for BAAI/bge-small-en-v1.5
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ── Performance Indexes ───────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_visits_patient    ON visits(patient_id, visit_date DESC);
CREATE INDEX IF NOT EXISTS idx_docs_patient      ON documents(patient_id, document_type);
CREATE INDEX IF NOT EXISTS idx_rx_patient        ON prescriptions(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_ch_visit          ON clinical_histories(visit_id);
CREATE INDEX IF NOT EXISTS idx_audit_user        ON audit_logs(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_embed_patient     ON embeddings(patient_id);

-- ── Seed Default Demo Accounts ────────────────────────────────────────────────
-- Only inserted if the tables are empty (idempotent seed)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM doctors WHERE doctor_id = 'DOC-101') THEN
    INSERT INTO doctors (doctor_id, name, department)
    VALUES ('DOC-101', 'Dr. A. Sharma', 'Cardiology');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pharmacists WHERE pharmacist_id = 'PHARM-101') THEN
    INSERT INTO pharmacists (pharmacist_id, name)
    VALUES ('PHARM-101', 'Pharmacy Specialist');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM patients WHERE patient_id = 'PAT-000001') THEN
    INSERT INTO patients (patient_id, name, date_of_birth, gender, phone, preferred_language)
    VALUES ('PAT-000001', 'Rajesh Kumar', '1984-05-12', 'Male', '9876543210', 'Telugu / English');
  END IF;
END
$$;

-- Note: user password hashes are seeded by the Python application on first startup
-- (via crud.seed_default_users) so that bcrypt is applied correctly.
