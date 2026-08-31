import hashlib
import os
import secrets
import hmac

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a unique random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100_000
    )
    return f"{salt}${key.hex()}"

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against stored salt and hash in constant time."""
    try:
        salt, stored_hash = hashed_password.split('$', 1)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100_000
        )
        return hmac.compare_digest(key.hex(), stored_hash)
    except Exception:
        return False
