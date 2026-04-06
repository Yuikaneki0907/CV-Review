from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.cv_file_repository import CVFileRepository
from app.infrastructure.storage.minio_storage import MinioFileStorage
from app.presentation.dependencies import get_current_user_id
from app.logger import get_logger

logger = get_logger("app.presentation.cv_files")

router = APIRouter(prefix="/cv-files", tags=["CV Files"])

# ── Response DTOs ────────────────────────────────────────────────

class CVFileResponse(BaseModel):
    id: UUID
    original_filename: str
    content_type: str
    file_size: int
    version: int
    analysis_id: Optional[UUID] = None
    created_at: datetime


class CVFileDownloadResponse(BaseModel):
    download_url: str
    filename: str
    expires_in: int


# ── Singleton storage ────────────────────────────────────────────

_file_storage: MinioFileStorage | None = None


def _get_file_storage() -> MinioFileStorage:
    global _file_storage
    if _file_storage is None:
        _file_storage = MinioFileStorage()
    return _file_storage


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/", response_model=List[CVFileResponse])
async def list_cv_files(
    limit: int = 20,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """List the current user's uploaded CV files with version info."""
    repo = CVFileRepository(session)
    files = await repo.list_by_user_id(user_id, limit, offset)
    return [
        CVFileResponse(
            id=f.id,
            original_filename=f.original_filename,
            content_type=f.content_type,
            file_size=f.file_size,
            version=f.version,
            analysis_id=f.analysis_id,
            created_at=f.created_at,
        )
        for f in files
    ]


@router.get("/{file_id}/download", response_model=CVFileDownloadResponse)
async def download_cv_file(
    file_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get a presigned download URL for a CV file."""
    repo = CVFileRepository(session)
    cv_file = await repo.get_by_id(file_id)

    if not cv_file or cv_file.user_id != user_id:
        raise HTTPException(status_code=404, detail="File not found")

    settings = get_settings()
    storage = _get_file_storage()
    url = storage.get_presigned_url(
        bucket=settings.MINIO_BUCKET_NAME,
        key=cv_file.storage_key,
        expires_seconds=3600,
    )

    return CVFileDownloadResponse(
        download_url=url,
        filename=cv_file.original_filename,
        expires_in=3600,
    )
