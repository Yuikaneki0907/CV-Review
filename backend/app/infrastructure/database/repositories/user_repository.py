from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.entities.password_reset_token import PasswordResetToken
from app.application.interfaces.repositories import IUserRepository
from app.infrastructure.database.models import UserModel, PasswordResetTokenModel


class UserRepository(IUserRepository):
    """Concrete implementation of IUserRepository using SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, user: User) -> User:
        db_user = UserModel(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            full_name=user.full_name,
        )
        self._session.add(db_user)
        await self._session.flush()
        return self._to_entity(db_user)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        db_user = result.scalar_one_or_none()
        return self._to_entity(db_user) if db_user else None

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        return self._to_entity(db_user) if db_user else None

    async def update(self, user_id: UUID, full_name: Optional[str] = None, phone_number: Optional[str] = None) -> Optional[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        if not db_user:
            return None
        
        if full_name is not None:
            db_user.full_name = full_name
        if phone_number is not None:
            db_user.phone_number = phone_number
            
        db_user.updated_at = datetime.utcnow()
        await self._session.flush()
        return self._to_entity(db_user)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> Optional[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        db_user = result.scalar_one_or_none()
        if not db_user:
            return None

        db_user.password_hash = password_hash
        db_user.updated_at = datetime.utcnow()
        await self._session.flush()
        return self._to_entity(db_user)

    async def create_password_reset_token(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        db_token = PasswordResetTokenModel(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(db_token)
        await self._session.flush()
        return self._to_password_reset_entity(db_token)

    async def get_valid_password_reset_token(self, token_hash: str) -> Optional[PasswordResetToken]:
        result = await self._session.execute(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.token_hash == token_hash,
                PasswordResetTokenModel.used_at.is_(None),
                PasswordResetTokenModel.expires_at > datetime.utcnow(),
            )
        )
        db_token = result.scalar_one_or_none()
        return self._to_password_reset_entity(db_token) if db_token else None

    async def invalidate_password_reset_tokens(self, user_id: UUID) -> None:
        await self._session.execute(
            update(PasswordResetTokenModel)
            .where(
                PasswordResetTokenModel.user_id == user_id,
                PasswordResetTokenModel.used_at.is_(None),
            )
            .values(used_at=datetime.utcnow())
        )
        await self._session.flush()

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            full_name=model.full_name,
            phone_number=model.phone_number,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_password_reset_entity(model: PasswordResetTokenModel) -> PasswordResetToken:
        return PasswordResetToken(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            created_at=model.created_at,
            used_at=model.used_at,
        )
