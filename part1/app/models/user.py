from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class UserRegister(BaseModel):
    full_name: str
    username: str
    email: str
    password: str
    phone: Optional[str] = None
    preferred_language: str = "en"

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class UserProfile(BaseModel):
    user_id: str
    full_name: str
    username: str
    email: str
    phone: Optional[str] = None
    preferred_language: str = "en"
    created_at: Optional[str] = None
