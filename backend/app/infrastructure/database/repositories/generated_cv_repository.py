from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.generated_cv import GeneratedCV
from app.application.interfaces.repositories import IGeneratedCVRepository
from app.infrastructure.database.models import GeneratedCVModel


class GeneratedCVRepository(IGeneratedCVRepository):
    """Concrete implementation of IGeneratedCVRepository using SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, cv: GeneratedCV) -> GeneratedCV:
        db_model = GeneratedCVModel(
            id=cv.id,
            user_id=cv.user_id,
            conversation_id=cv.conversation_id,
            version=cv.version,
            parent_version_id=cv.parent_version_id,
            target_jd_text=cv.target_jd_text,
            base_profile_data=cv.base_profile_data,
            generated_content=cv.generated_content,
            status=cv.status,
            created_at=cv.created_at,
        )
        self._session.add(db_model)
        await self._session.flush()
        return cv

    async def get_by_id(self, cv_id: UUID) -> Optional[GeneratedCV]:
        result = await self._session.execute(
            select(GeneratedCVModel)
            .where(GeneratedCVModel.id == cv_id, GeneratedCVModel.deleted_at.is_(None))
        )
        db_model = result.scalar_one_or_none()
        return self._to_entity(db_model) if db_model else None

    async def list_by_user_id(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> List[GeneratedCV]:
        latest_versions = (
            select(
                GeneratedCVModel.conversation_id.label("conversation_id"),
                func.max(GeneratedCVModel.version).label("max_version"),
            )
            .where(
                GeneratedCVModel.user_id == user_id,
                GeneratedCVModel.deleted_at.is_(None),
            )
            .group_by(GeneratedCVModel.conversation_id)
            .subquery()
        )

        result = await self._session.execute(
            select(GeneratedCVModel)
            .join(
                latest_versions,
                and_(
                    GeneratedCVModel.conversation_id == latest_versions.c.conversation_id,
                    GeneratedCVModel.version == latest_versions.c.max_version,
                ),
            )
            .where(
                GeneratedCVModel.user_id == user_id,
                GeneratedCVModel.deleted_at.is_(None),
            )
            .order_by(GeneratedCVModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update_generated_content(
        self,
        cv_id: UUID,
        user_id: UUID,
        generated_content: dict,
    ) -> Optional[GeneratedCV]:
        result = await self._session.execute(
            select(GeneratedCVModel).where(
                GeneratedCVModel.id == cv_id,
                GeneratedCVModel.user_id == user_id,
                GeneratedCVModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        model.generated_content = generated_content
        await self._session.flush()
        return self._to_entity(model)

    async def get_next_version(self, user_id: UUID, conversation_id: UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(GeneratedCVModel.version), 0)).where(
                GeneratedCVModel.user_id == user_id,
                GeneratedCVModel.conversation_id == conversation_id,
                GeneratedCVModel.deleted_at.is_(None),
            )
        )
        current_max = int(result.scalar_one())
        return current_max + 1

    async def list_versions(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> List[GeneratedCV]:
        result = await self._session.execute(
            select(GeneratedCVModel)
            .where(
                GeneratedCVModel.user_id == user_id,
                GeneratedCVModel.conversation_id == conversation_id,
                GeneratedCVModel.deleted_at.is_(None),
            )
            .order_by(GeneratedCVModel.version.desc(), GeneratedCVModel.created_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def soft_delete(self, cv_id: UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            select(GeneratedCVModel)
            .where(GeneratedCVModel.id == cv_id, GeneratedCVModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return False

        deleted_at = datetime.now(timezone.utc)
        await self._session.execute(
            update(GeneratedCVModel)
            .where(
                GeneratedCVModel.user_id == user_id,
                GeneratedCVModel.conversation_id == model.conversation_id,
                GeneratedCVModel.deleted_at.is_(None),
            )
            .values(deleted_at=deleted_at)
        )
        await self._session.flush()
        return True

    @staticmethod
    def _to_entity(model: GeneratedCVModel) -> GeneratedCV:
        return GeneratedCV(
            id=model.id,
            user_id=model.user_id,
            conversation_id=model.conversation_id,
            version=int(model.version),
            parent_version_id=model.parent_version_id,
            target_jd_text=model.target_jd_text,
            base_profile_data=model.base_profile_data,
            generated_content=model.generated_content,
            status=model.status,
            created_at=model.created_at,
            deleted_at=model.deleted_at,
        )
