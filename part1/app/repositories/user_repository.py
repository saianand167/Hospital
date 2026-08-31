import json
from typing import Optional
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.user import UserProfile, UserRegister

class UserRepository:
    @staticmethod
    def create_user(user_in: UserRegister) -> UserProfile:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Check unique username or email
            cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (user_in.username, user_in.email))
            if cursor.fetchone():
                raise ValueError("Username or Email already registered")
                
            # Count users to generate sequential USR-000001
            cursor.execute("SELECT COUNT(id) FROM users")
            count = cursor.fetchone()[0] + 1
            user_id = f"USR-{count:06d}"
            
            pwd_hash = hash_password(user_in.password)
            cursor.execute("""
                INSERT INTO users (user_id, full_name, username, email, password_hash, phone, preferred_language)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, user_in.full_name, user_in.username, user_in.email, pwd_hash, user_in.phone, user_in.preferred_language))
            
            return UserProfile(
                user_id=user_id,
                full_name=user_in.full_name,
                username=user_in.username,
                email=user_in.email,
                phone=user_in.phone,
                preferred_language=user_in.preferred_language
            )

    @staticmethod
    def authenticate_user(username_or_email: str, password: str) -> Optional[UserProfile]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, full_name, username, email, password_hash, phone, preferred_language, created_at
                FROM users
                WHERE username = ? OR email = ? OR user_id = ?
            """, (username_or_email, username_or_email, username_or_email))
            row = cursor.fetchone()
            if not row:
                return None
            
            if not verify_password(password, row["password_hash"]):
                return None
                
            return UserProfile(
                user_id=row["user_id"],
                full_name=row["full_name"],
                username=row["username"],
                email=row["email"],
                phone=row["phone"],
                preferred_language=row["preferred_language"],
                created_at=str(row["created_at"])
            )

    @staticmethod
    def get_by_user_id(user_id: str) -> Optional[UserProfile]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, full_name, username, email, phone, preferred_language, created_at
                FROM users WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return UserProfile(
                user_id=row["user_id"],
                full_name=row["full_name"],
                username=row["username"],
                email=row["email"],
                phone=row["phone"],
                preferred_language=row["preferred_language"],
                created_at=str(row["created_at"])
            )
