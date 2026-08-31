from fastapi import APIRouter, HTTPException, status
from app.models.user import UserRegister, UserLogin, UserProfile
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserRegister):
    try:
        return AuthService.register(user_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=UserProfile)
def login_user(login_in: UserLogin):
    user = AuthService.login(login_in)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/email or password")
    return user

@router.get("/profile/{user_id}", response_model=UserProfile)
def get_profile(user_id: str):
    user = AuthService.get_profile(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
