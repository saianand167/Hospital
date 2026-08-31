import json
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.models.consultation import ConsultationSummary

class ConsultationRepository:
    @staticmethod
    def create_consultation(user_id: str, language: str = "en", complaint: Optional[str] = None) -> str:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Ensure user exists for foreign key integrity
            cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, full_name, username, email, password_hash, preferred_language)
                    VALUES (?, ?, ?, ?, 'system_default_hash', ?)
                """, (user_id, f"Patient {user_id}", f"user_{user_id.lower()}", f"{user_id.lower()}@medikiosk.local", language))
            
            cursor.execute("SELECT COUNT(id) FROM consultations")
            count = cursor.fetchone()[0] + 1
            visit_id = f"VIS-{count:06d}"
            
            cursor.execute("""
                INSERT INTO consultations (visit_id, user_id, language, current_complaint, status)
                VALUES (?, ?, ?, ?, 'active')
            """, (visit_id, user_id, language, complaint))
            
            return visit_id


    @staticmethod
    def get_by_visit_id(visit_id: str) -> Optional[dict]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT visit_id, user_id, language, current_complaint, status, started_at, completed_at, triage_flag, triage_priority
                FROM consultations WHERE visit_id = ?
            """, (visit_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_by_user(user_id: str) -> List[ConsultationSummary]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT visit_id, user_id, language, current_complaint, status, started_at, completed_at, triage_flag, triage_priority
                FROM consultations WHERE user_id = ?
                ORDER BY id DESC
            """, (user_id,))
            rows = cursor.fetchall()
            return [
                ConsultationSummary(
                    visit_id=row["visit_id"],
                    user_id=row["user_id"],
                    language=row["language"],
                    current_complaint=row["current_complaint"],
                    status=row["status"],
                    started_at=str(row["started_at"]),
                    completed_at=str(row["completed_at"]) if row["completed_at"] else None,
                    triage_flag=row["triage_flag"] or "GREEN",
                    triage_priority=bool(row["triage_priority"])
                )
                for row in rows
            ]

    @staticmethod
    def update_complaint(visit_id: str, complaint: str):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE consultations SET current_complaint = ? WHERE visit_id = ?", (complaint, visit_id))

    @staticmethod
    def update_triage_and_status(visit_id: str, status: str, flag: str, priority: bool, completed: bool = False):
        with get_db() as conn:
            cursor = conn.cursor()
            comp_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if completed else None
            cursor.execute("""
                UPDATE consultations
                SET status = ?, triage_flag = ?, triage_priority = ?, completed_at = COALESCE(?, completed_at)
                WHERE visit_id = ?
            """, (status, flag, 1 if priority else 0, comp_time, visit_id))

    @staticmethod
    def save_final_history(visit_id: str, user_id: str, history_dict: dict):
        with get_db() as conn:
            cursor = conn.cursor()
            history_json = json.dumps(history_dict, ensure_ascii=False)
            cursor.execute("""
                INSERT OR REPLACE INTO final_histories (visit_id, user_id, history_json)
                VALUES (?, ?, ?)
            """, (visit_id, user_id, history_json))

    @staticmethod
    def get_final_history(visit_id: str) -> Optional[dict]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT history_json FROM final_histories WHERE visit_id = ?", (visit_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return json.loads(row["history_json"])
