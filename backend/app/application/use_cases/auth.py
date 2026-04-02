from datetime import datetime, timedelta

import bcrypt
from jose import jwt

from app.config import get_settings
from app.domain.entities.user import User
from app.application.interfaces.repositories import IUserRepository


def _hash_password(password: str) -> str:
    """Hash password using bcrypt directly (compatible with bcrypt 5.x)."""
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class AuthUseCase:
    """Handles user registration and login."""

    def __init__(self, user_repo: IUserRepository):
        self._user_repo = user_repo

    async def register(self, email: str, password: str, full_name: str) -> User:
        # Check existing
        existing = await self._user_repo.get_by_email(email)
        if existing:
            raise ValueError("Email đã được sử dụng")

        user = User(
            email=email,
            password_hash=_hash_password(password),
            full_name=full_name,
        )
        return await self._user_repo.create(user)

    async def login(self, email: str, password: str) -> str:
        user = await self._user_repo.get_by_email(email)
        if not user or not _verify_password(password, user.password_hash):
            raise ValueError("Email hoặc mật khẩu không đúng")

        return self._create_token(str(user.id))

    def _create_token(self, user_id: str) -> str:
        settings = get_settings()
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": user_id, "exp": expire}
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
