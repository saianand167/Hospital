"""
SIH26047 MediKiosk — SQLite to PostgreSQL Migration Script
Migrates patient accounts, consultation records, and clinical histories
from Part 1's local SQLite database into the unified PostgreSQL database.

Usage:
    python scripts/migrate_sqlite_to_postgres.py [--sqlite-path part1/medikiosk.db]
"""

import sys
import os
import json
import sqlite3
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import SessionLocal, check_db_health
from database import models

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration")

def migrate(sqlite_db_path: Path):
    if not sqlite_db_path.exists():
        logger.warning(f"SQLite database not found at {sqlite_db_path}. Nothing to migrate.")
        return

    logger.info(f"Connecting to SQLite: {sqlite_db_path}")
    sq_conn = sqlite3.connect(str(sqlite_db_path))
    sq_conn.row_factory = sqlite3.Row
    sq_cur = sq_conn.cursor()

    # Check PostgreSQL connection
    if not check_db_health():
        logger.error("Cannot connect to PostgreSQL server! Ensure Docker PostgreSQL is running.")
        sys.exit(1)

    pg_db = SessionLocal()
    try:
        # 1. Migrate Users & Patients
        logger.info("Migrating users/patients...")
        user_mapping = {}  # USR-XXXXXX -> PAT-XXXXXX

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM users")
            users = sq_cur.fetchall()
            for u in users:
                old_uid = u["user_id"]
                # Generate matching PAT-XXXXXX format
                pat_id = old_uid.replace("USR-", "PAT-") if old_uid.startswith("USR-") else f"PAT-{old_uid}"
                user_mapping[old_uid] = pat_id

                # Upsert Patient
                existing_pat = pg_db.query(models.Patient).filter(models.Patient.patient_id == pat_id).first()
                if not existing_pat:
                    new_pat = models.Patient(
                        patient_id=pat_id,
                        name=u["full_name"],
                        email=u["email"],
                        phone=u["phone"],
                        preferred_language=u["preferred_language"] or "English"
                    )
                    pg_db.add(new_pat)
                    pg_db.flush()
                    logger.info(f"Created Patient: {pat_id} ({u['full_name']})")

                # Upsert User
                existing_user = pg_db.query(models.User).filter(models.User.username == u["username"]).first()
                if not existing_user:
                    new_user = models.User(
                        username=u["username"],
                        password_hash=u["password_hash"],
                        role="PATIENT",
                        patient_id=pat_id
                    )
                    pg_db.add(new_user)
                    pg_db.flush()
                    logger.info(f"Created User: {u['username']} linked to {pat_id}")

        # 2. Migrate Consultations -> Visits
        logger.info("Migrating consultations to visits...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='consultations'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM consultations")
            consultations = sq_cur.fetchall()
            for c in consultations:
                vid = c["visit_id"]
                old_uid = c["user_id"]
                pat_id = user_mapping.get(old_uid, old_uid.replace("USR-", "PAT-"))

                # Ensure patient exists
                if not pg_db.query(models.Patient).filter(models.Patient.patient_id == pat_id).first():
                    pg_db.add(models.Patient(patient_id=pat_id, name=f"Patient {pat_id}"))
                    pg_db.flush()

                existing_visit = pg_db.query(models.Visit).filter(models.Visit.visit_id == vid).first()
                if not existing_visit:
                    prio = "HIGH" if c["triage_flag"] in ["RED", "YELLOW"] else "NORMAL"
                    new_visit = models.Visit(
                        visit_id=vid,
                        patient_id=pat_id,
                        status="COMPLETED" if c["status"] == "completed" else "WAITING",
                        priority=prio
                    )
                    pg_db.add(new_visit)
                    pg_db.flush()
                    logger.info(f"Created Visit: {vid} for patient {pat_id}")

        # 3. Migrate Final Histories -> Clinical Histories
        logger.info("Migrating final histories...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='final_histories'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM final_histories")
            histories = sq_cur.fetchall()
            for h in histories:
                vid = h["visit_id"]
                old_uid = h["user_id"]
                pat_id = user_mapping.get(old_uid, old_uid.replace("USR-", "PAT-"))

                try:
                    h_json = json.loads(h["history_json"])
                except Exception:
                    h_json = {"raw": h["history_json"]}

                existing_ch = pg_db.query(models.ClinicalHistory).filter(models.ClinicalHistory.visit_id == vid).first()
                if not existing_ch:
                    new_ch = models.ClinicalHistory(
                        visit_id=vid,
                        patient_id=pat_id,
                        history_json=h_json,
                        source="Part1_SQLite_Migration"
                    )
                    pg_db.add(new_ch)
                    logger.info(f"Created ClinicalHistory for visit {vid}")

        pg_db.commit()
        logger.info("✅ Migration completed successfully and committed to PostgreSQL.")

    except Exception as e:
        pg_db.rollback()
        logger.error(f"Migration failed: {e}", exc_info=True)
    finally:
        pg_db.close()
        sq_conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL for MediKiosk")
    parser.add_argument("--sqlite-path", default=str(PROJECT_ROOT / "part1" / "medikiosk.db"), help="Path to SQLite DB")
    args = parser.parse_args()
    migrate(Path(args.sqlite_path))
