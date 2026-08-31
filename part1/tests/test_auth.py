import pytest
import uuid
from app.services.auth_service import AuthService
from app.models.user import UserRegister, UserLogin

def test_user_registration_and_unique_id():
    """Test user registration generates sequential USR-XXXXXX ID."""
    uid = uuid.uuid4().hex[:6]
    reg = UserRegister(
        full_name="Sai Anand",
        username=f"sai_{uid}",
        email=f"sai_{uid}@example.com",
        password="securepassword123",
        phone="9876543210",
        preferred_language="te"
    )
    user = AuthService.register(reg)
    assert user.user_id.startswith("USR-")
    assert user.full_name == "Sai Anand"
    assert user.preferred_language == "te"

def test_user_login_success():
    """Test login with correct username and password."""
    uid = uuid.uuid4().hex[:6]
    reg = UserRegister(
        full_name="Test User",
        username=f"user_{uid}",
        email=f"user_{uid}@example.com",
        password="mypassword456"
    )
    AuthService.register(reg)

    user = AuthService.login(UserLogin(username_or_email=f"user_{uid}", password="mypassword456"))
    assert user is not None
    assert user.username == f"user_{uid}"

def test_user_login_incorrect_password():
    """Test login with wrong password fails securely."""
    uid = uuid.uuid4().hex[:6]
    reg = UserRegister(
        full_name="Test User",
        username=f"user_pwd_{uid}",
        email=f"user_pwd_{uid}@example.com",
        password="mypassword456"
    )
    AuthService.register(reg)
    user = AuthService.login(UserLogin(username_or_email=f"user_pwd_{uid}", password="wrongpassword"))
    assert user is None

def test_user_registration_duplicate_username_fails():
    """Test duplicate username is rejected."""
    uid = uuid.uuid4().hex[:6]
    reg = UserRegister(
        full_name="Duplicate User",
        username=f"dup_{uid}",
        email=f"dup_{uid}@example.com",
        password="password123"
    )
    AuthService.register(reg)
    with pytest.raises(ValueError):
        AuthService.register(reg)
