from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.application.interfaces.repositories import IUserRepository
from app.infrastructure.database.models import UserModel


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
        from datetime import datetime, timezone
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
            
        db_user.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return self._to_entity(db_user)

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            full_name=model.full_name,
            created_at=model.created_at,
        )
