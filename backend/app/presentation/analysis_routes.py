import os
import shutil
import traceback
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.application.dto.responses import (
    AnalysisResponse,
    AnalysisListResponse,
    ScoreResponse,
    SkillResponse,
    DiffSegmentResponse,
    HallucinationWarningResponse,
)
from app.domain.entities.analysis_result import AnalysisResult
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.file_parsers.parsers import get_parser
from app.infrastructure.celery.tasks import run_analysis_task
from app.presentation.dependencies import get_current_user_id
from app.logger import get_logger

logger = get_logger("app.presentation.analysis")

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post("/", response_model=AnalysisResponse, status_code=201)
async def create_analysis(
    cv_file: UploadFile = File(...),
    jd_text: str = Form(...),
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Upload CV + paste JD, then kick off analysis."""

    settings = get_settings()

    # Validate file type
    if not cv_file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    logger.info(
        "Upload CV: user_id=%s, filename=%s, content_type=%s",
        user_id, cv_file.filename, cv_file.content_type,
    )

    try:
        parser = get_parser(cv_file.filename)
    except ValueError:
        logger.warning("Unsupported file type: filename=%s", cv_file.filename)
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF hoặc DOCX")

    # Save file
    file_id = str(uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(cv_file.filename)[1]
    file_path = os.path.join(upload_dir, f"{file_id}{ext}")

    with open(file_path, "wb") as f:
        shutil.copyfileobj(cv_file.file, f)

    file_size = os.path.getsize(file_path)
    logger.info("File saved: path=%s, size=%d bytes", file_path, file_size)

    # Parse file
    try:
        cv_text = await parser.parse(file_path)
        logger.info("File parsed: %d characters extracted", len(cv_text))
    except Exception as e:
        logger.error("File parse FAILED: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Không đọc được file: {e}")

    # Create analysis record
    analysis_repo = AnalysisRepository(session)
    analysis = AnalysisResult(
        user_id=user_id,
        cv_filename=cv_file.filename,
        cv_text=cv_text,
        jd_text=jd_text,
    )
    await analysis_repo.create(analysis)
    await session.commit()

    logger.info(
        "Analysis created: analysis_id=%s, user_id=%s → dispatching to Celery",
        analysis.id, user_id,
    )

    # Dispatch to Celery
    run_analysis_task.delay(str(analysis.id))

    return _to_response(analysis)


@router.get("/", response_model=List[AnalysisListResponse])
async def list_analyses(
    limit: int = 20,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """List user's analysis history."""
    logger.debug("List analyses: user_id=%s, limit=%d, offset=%d", user_id, limit, offset)
    analysis_repo = AnalysisRepository(session)
    analyses = await analysis_repo.get_by_user_id(user_id, limit, offset)
    logger.debug("Returned %d analyses for user_id=%s", len(analyses), user_id)
    return [
        AnalysisListResponse(
            id=a.id,
            status=a.status.value,
            cv_filename=a.cv_filename,
            overall_score=a.score.overall if a.score else None,
            created_at=a.created_at,
        )
        for a in analyses
    ]


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get full analysis details."""
    logger.debug("Get analysis: analysis_id=%s, user_id=%s", analysis_id, user_id)
    analysis_repo = AnalysisRepository(session)
    analysis = await analysis_repo.get_by_id(analysis_id)

    if not analysis or analysis.user_id != user_id:
        logger.warning(
            "Analysis not found or forbidden: analysis_id=%s, user_id=%s",
            analysis_id, user_id,
        )
        raise HTTPException(status_code=404, detail="Không tìm thấy kết quả phân tích")

    return _to_response(analysis)


def _to_response(analysis: AnalysisResult) -> AnalysisResponse:
    """Map domain entity to API response DTO."""

    score = None
    if analysis.score:
        score = ScoreResponse(
            overall=analysis.score.overall,
            skills_score=analysis.score.skills_score,
            experience_score=analysis.score.experience_score,
            tools_score=analysis.score.tools_score,
        )

    matched = None
    missing = None
    extra = None
    if analysis.skill_analysis:
        matched = [
            SkillResponse(name=s.name, category=s.category) for s in analysis.skill_analysis.matched_skills
        ]
        missing = [
            SkillResponse(name=s.name, category=s.category) for s in analysis.skill_analysis.missing_skills
        ]
        extra = [
            SkillResponse(name=s.name, category=s.category) for s in analysis.skill_analysis.extra_skills
        ]

    diff_segments = None
    if analysis.diff_result:
        diff_segments = [
            DiffSegmentResponse(text=seg.text, diff_type=seg.diff_type.value)
            for seg in analysis.diff_result.segments
        ]

    warnings = None
    if analysis.hallucination_report:
        warnings = [
            HallucinationWarningResponse(
                section=w.section,
                original_text=w.original_text,
                rewritten_text=w.rewritten_text,
                issue_type=w.issue_type,
                explanation=w.explanation,
                level=w.level.value,
            )
            for w in analysis.hallucination_report.warnings
        ]

    return AnalysisResponse(
        id=analysis.id,
        status=analysis.status.value,
        cv_filename=analysis.cv_filename,
        jd_text=analysis.jd_text,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        cv_extracted=analysis.cv_extracted,
        jd_extracted=analysis.jd_extracted,
        score=score,
        matched_skills=matched,
        missing_skills=missing,
        extra_skills=extra,
        rewritten_cv=analysis.rewritten_cv,
        diff_segments=diff_segments,
        hallucination_warnings=warnings,
    )
