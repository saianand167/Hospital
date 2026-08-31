from typing import Optional
from app.repositories.user_repository import UserRepository
from app.models.user import UserRegister, UserLogin, UserProfile

class AuthService:
    @staticmethod
    def register(user_in: UserRegister) -> UserProfile:
        return UserRepository.create_user(user_in)

    @staticmethod
    def login(login_in: UserLogin) -> Optional[UserProfile]:
        return UserRepository.authenticate_user(
            username_or_email=login_in.username_or_email,
            password=login_in.password
        )

    @staticmethod
    def get_profile(user_id: str) -> Optional[UserProfile]:
        return UserRepository.get_by_user_id(user_id)
