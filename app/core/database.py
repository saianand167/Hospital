import sqlite3
from pathlib import Path
from contextlib import contextmanager
from app.core.config import settings

DB_FILE = settings.BASE_DIR / "medikiosk.db"

def init_db(db_path: Path = DB_FILE):
    """Initialize SQLite database schemas with proper foreign keys."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # 1. users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        preferred_language TEXT DEFAULT 'en',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. consultations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consultations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id TEXT UNIQUE NOT NULL,
        user_id TEXT NOT NULL,
        language TEXT DEFAULT 'en',
        current_complaint TEXT,
        status TEXT DEFAULT 'active',
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        triage_flag TEXT DEFAULT 'GREEN',
        triage_priority INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    # 3. questions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id TEXT UNIQUE NOT NULL,
        question_key TEXT NOT NULL,
        question_text TEXT NOT NULL,
        language TEXT DEFAULT 'en',
        input_type TEXT DEFAULT 'text',
        priority INTEGER DEFAULT 10
    );
    """)

    # 4. answers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        answer_id TEXT UNIQUE NOT NULL,
        visit_id TEXT NOT NULL,
        question_id TEXT,
        user_id TEXT NOT NULL,
        question_text TEXT NOT NULL,
        answer_text TEXT NOT NULL,
        input_mode TEXT DEFAULT 'text',
        language TEXT DEFAULT 'en',
        structured_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (visit_id) REFERENCES consultations(visit_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    # 5. triage_events table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS triage_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id TEXT NOT NULL,
        rule_id TEXT NOT NULL,
        flag TEXT NOT NULL,
        priority INTEGER DEFAULT 0,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (visit_id) REFERENCES consultations(visit_id)
    );
    """)

    # 6. final_histories table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS final_histories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id TEXT UNIQUE NOT NULL,
        user_id TEXT NOT NULL,
        history_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        engine_version TEXT DEFAULT '1.0',
        FOREIGN KEY (visit_id) REFERENCES consultations(visit_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    conn.commit()
    conn.close()

@contextmanager
def get_db(db_path: Path = DB_FILE):
    """Context manager for SQLite database connection."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

