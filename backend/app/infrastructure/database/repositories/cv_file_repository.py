from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.repositories import ICVFileRepository
from app.domain.entities.cv_file import CVFile
from app.infrastructure.database.models import CVFileModel


class CVFileRepository(ICVFileRepository):
    """SQLAlchemy implementation of ICVFileRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, cv_file: CVFile) -> CVFile:
        model = CVFileModel(
            id=cv_file.id,
            user_id=cv_file.user_id,
            analysis_id=cv_file.analysis_id,
            original_filename=cv_file.original_filename,
            storage_key=cv_file.storage_key,
            content_type=cv_file.content_type,
            file_size=cv_file.file_size,
            version=cv_file.version,
            created_at=cv_file.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return cv_file

    async def get_by_id(self, file_id: UUID) -> Optional[CVFile]:
        result = await self._session.execute(
            select(CVFileModel).where(CVFileModel.id == file_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def list_by_user_id(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> List[CVFile]:
        result = await self._session.execute(
            select(CVFileModel)
            .where(CVFileModel.user_id == user_id)
            .order_by(CVFileModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_next_version(self, user_id: UUID, filename: str) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(CVFileModel.version), 0)).where(
                CVFileModel.user_id == user_id,
                CVFileModel.original_filename == filename,
            )
        )
        current_max = int(result.scalar_one())
        return current_max + 1

    @staticmethod
    def _to_entity(model: CVFileModel) -> CVFile:
        return CVFile(
            id=model.id,
            user_id=model.user_id,
            analysis_id=model.analysis_id,
            original_filename=model.original_filename,
            storage_key=model.storage_key,
            content_type=model.content_type,
            file_size=int(model.file_size),
            version=int(model.version),
            created_at=model.created_at,
        )
