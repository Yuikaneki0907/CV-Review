import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode

import bcrypt
from jose import jwt

from app.config import get_settings
from app.domain.entities.user import User
from app.application.interfaces.repositories import IUserRepository
from app.infrastructure.notifications.email_service import EmailDeliveryError, SMTPEmailService


@dataclass
class ForgotPasswordResult:
    message: str
    email_sent: bool = False
    debug_reset_url: str | None = None
    debug_reset_token: str | None = None


@dataclass
class MessageResult:
    message: str


PASSWORD_REQUIREMENT_MESSAGE = "Mật khẩu phải có chữ hoa, chữ thường, số, ký tự đặc biệt và dài hơn 8 ký tự."


def _validate_password_strength(password: str) -> None:
    if (
        len(password) <= 8
        or not re.search(r"[A-Z]", password)
        or not re.search(r"[a-z]", password)
        or not re.search(r"\d", password)
        or not re.search(r"[^A-Za-z0-9]", password)
    ):
        raise ValueError(PASSWORD_REQUIREMENT_MESSAGE)


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

    def __init__(
        self,
        user_repo: IUserRepository,
        email_service: SMTPEmailService | None = None,
    ):
        self._user_repo = user_repo
        self._email_service = email_service or SMTPEmailService()

    async def register(self, email: str, password: str, full_name: str) -> User:
        _validate_password_strength(password)

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

    async def request_password_reset(self, email: str) -> ForgotPasswordResult:
        settings = get_settings()
        generic_message = "Nếu email tồn tại, hệ thống sẽ gửi hướng dẫn đặt lại mật khẩu."

        if not self._email_service.is_configured() and not settings.DEBUG:
            raise RuntimeError("Chức năng quên mật khẩu chưa được cấu hình email")

        user = await self._user_repo.get_by_email(email)
        if not user:
            return ForgotPasswordResult(message=generic_message)

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_reset_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        reset_url = _build_reset_url(settings.FRONTEND_URL, raw_token)

        await self._user_repo.invalidate_password_reset_tokens(user.id)
        await self._user_repo.create_password_reset_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        email_sent = False
        if self._email_service.is_configured():
            try:
                await self._email_service.send_password_reset_email(
                    recipient_email=user.email,
                    recipient_name=user.full_name,
                    reset_url=reset_url,
                    expire_minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
                )
                email_sent = True
            except EmailDeliveryError:
                if not settings.DEBUG:
                    raise RuntimeError("Không thể gửi email đặt lại mật khẩu lúc này")

        if settings.DEBUG and not email_sent:
            return ForgotPasswordResult(
                message=generic_message,
                email_sent=False,
                debug_reset_url=reset_url,
                debug_reset_token=raw_token,
            )

        return ForgotPasswordResult(message=generic_message, email_sent=email_sent)

    async def reset_password(self, token: str, new_password: str) -> MessageResult:
        reset_token = await self._user_repo.get_valid_password_reset_token(
            _hash_reset_token(token)
        )
        if not reset_token:
            raise ValueError("Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn")

        _validate_password_strength(new_password)

        updated_user = await self._user_repo.update_password_hash(
            user_id=reset_token.user_id,
            password_hash=_hash_password(new_password),
        )
        if not updated_user:
            raise ValueError("Người dùng không tồn tại")

        await self._user_repo.invalidate_password_reset_tokens(reset_token.user_id)
        return MessageResult(message="Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại.")

    def _create_token(self, user_id: str) -> str:
        settings = get_settings()
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": user_id, "exp": expire}
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_reset_url(frontend_url: str, token: str) -> str:
    base_url = frontend_url.rstrip("/") or "http://localhost:3020"
    return f"{base_url}/reset-password?{urlencode({'token': token})}"
