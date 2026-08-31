import json
from typing import List, Optional, Dict, Any
from app.core.database import get_db
from app.models.answer import AnswerRecord

class AnswerRepository:
    @staticmethod
    def save_answer(
        visit_id: str,
        user_id: str,
        question_text: str,
        answer_text: str,
        input_mode: str = "text",
        language: str = "en",
        question_id: Optional[str] = None,
        structured_data: Optional[Dict[str, Any]] = None
    ) -> str:
        with get_db() as conn:
            cursor = conn.cursor()

            # Ensure user exists for foreign key integrity
            cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, full_name, username, email, password_hash, preferred_language)
                    VALUES (?, ?, ?, ?, 'system_default_hash', ?)
                """, (user_id, f"Patient {user_id}", f"user_{user_id.lower()}", f"{user_id.lower()}@medikiosk.local", language))

            # Ensure consultation exists for foreign key integrity
            cursor.execute("SELECT id FROM consultations WHERE visit_id = ?", (visit_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT OR IGNORE INTO consultations (visit_id, user_id, language, status)
                    VALUES (?, ?, ?, 'active')
                """, (visit_id, user_id, language))

            cursor.execute("SELECT COUNT(id) FROM answers")
            count = cursor.fetchone()[0] + 1
            answer_id = f"ANS-{count:06d}"
            
            struct_json = json.dumps(structured_data, ensure_ascii=False) if structured_data else None
            cursor.execute("""
                INSERT INTO answers (answer_id, visit_id, question_id, user_id, question_text, answer_text, input_mode, language, structured_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (answer_id, visit_id, question_id, user_id, question_text, answer_text, input_mode, language, struct_json))
            
            return answer_id

    @staticmethod
    def get_by_visit_id(visit_id: str) -> List[AnswerRecord]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT answer_id, visit_id, question_id, user_id, question_text, answer_text, input_mode, language, structured_data, created_at
                FROM answers WHERE visit_id = ?
                ORDER BY id ASC
            """, (visit_id,))
            rows = cursor.fetchall()
            
            records = []
            for r in rows:
                s_data = json.loads(r["structured_data"]) if r["structured_data"] else None
                records.append(AnswerRecord(
                    answer_id=r["answer_id"],
                    visit_id=r["visit_id"],
                    question_id=r["question_id"],
                    user_id=r["user_id"],
                    question_text=r["question_text"],
                    answer_text=r["answer_text"],
                    input_mode=r["input_mode"],
                    language=r["language"],
                    structured_data=s_data,
                    created_at=str(r["created_at"])
                ))
            return records
