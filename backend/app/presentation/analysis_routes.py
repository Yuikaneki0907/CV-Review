import asyncio
import json
import os
import tempfile
import traceback
from io import BytesIO
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
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
from app.domain.entities.cv_file import CVFile
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.cv_file_repository import CVFileRepository
from app.infrastructure.storage.minio_storage import MinioFileStorage
from app.infrastructure.file_parsers.parsers import get_parser
from app.infrastructure.celery.tasks import run_analysis_task
from app.presentation.dependencies import get_current_user_id
from app.logger import get_logger

logger = get_logger("app.presentation.analysis")

router = APIRouter(prefix="/analysis", tags=["Analysis"])

# Singleton – created once on first request
_file_storage: MinioFileStorage | None = None


def _get_file_storage() -> MinioFileStorage:
    global _file_storage
    if _file_storage is None:
        _file_storage = MinioFileStorage()
    return _file_storage


@router.post("/", response_model=AnalysisResponse, status_code=201)
async def create_analysis(
    cv_file: UploadFile = File(...),
    jd_text: str = Form(""),
    jd_file: UploadFile | None = File(None),
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Upload CV + (paste JD text OR upload JD file), then kick off analysis."""

    settings = get_settings()

    # ── Validate: must provide at least jd_text or jd_file ───────
    if not jd_text.strip() and (jd_file is None or not jd_file.filename):
        raise HTTPException(
            status_code=400,
            detail="Cần nhập Job Description (dán text hoặc upload file)",
        )

    # ── Validate CV file type ────────────────────────────────────
    if not cv_file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    logger.info(
        "Upload CV: user_id=%s, filename=%s, content_type=%s",
        user_id, cv_file.filename, cv_file.content_type,
    )

    try:
        cv_parser = get_parser(cv_file.filename)
    except ValueError:
        logger.warning("Unsupported file type: filename=%s", cv_file.filename)
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF hoặc DOCX")

    # ── Read CV bytes ────────────────────────────────────────────
    file_bytes = await cv_file.read()
    file_size = len(file_bytes)
    ext = os.path.splitext(cv_file.filename)[1]
    file_id = uuid4()

    # ── Upload CV to MinIO ───────────────────────────────────────
    storage = _get_file_storage()
    storage_key = f"{user_id}/{file_id}{ext}"
    content_type = cv_file.content_type or "application/octet-stream"

    storage.upload(
        bucket=settings.MINIO_BUCKET_NAME,
        key=storage_key,
        data=BytesIO(file_bytes),
        length=file_size,
        content_type=content_type,
    )
    logger.info("CV uploaded to MinIO: key=%s, size=%d bytes", storage_key, file_size)

    # ── Parse CV (write temp file for parser) ────────────────────
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        cv_text = await cv_parser.parse(tmp_path)
        logger.info("CV parsed: %d characters extracted", len(cv_text))
    except Exception as e:
        logger.error("CV parse FAILED: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Không đọc được file CV: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # ── Handle JD: file upload takes priority over text ──────────
    jd_final_text = jd_text.strip()

    if jd_file is not None and jd_file.filename:
        logger.info(
            "Upload JD file: user_id=%s, filename=%s, content_type=%s",
            user_id, jd_file.filename, jd_file.content_type,
        )
        try:
            jd_parser = get_parser(jd_file.filename)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="JD file: chỉ hỗ trợ PDF hoặc DOCX",
            )

        jd_bytes = await jd_file.read()
        jd_ext = os.path.splitext(jd_file.filename)[1]

        # Upload JD to MinIO (subfolder jd/)
        jd_file_id = uuid4()
        jd_storage_key = f"{user_id}/jd/{jd_file_id}{jd_ext}"
        jd_content_type = jd_file.content_type or "application/octet-stream"

        storage.upload(
            bucket=settings.MINIO_BUCKET_NAME,
            key=jd_storage_key,
            data=BytesIO(jd_bytes),
            length=len(jd_bytes),
            content_type=jd_content_type,
        )
        logger.info("JD uploaded to MinIO: key=%s, size=%d bytes", jd_storage_key, len(jd_bytes))

        # Parse JD file
        try:
            with tempfile.NamedTemporaryFile(suffix=jd_ext, delete=False) as jtmp:
                jtmp.write(jd_bytes)
                jd_tmp_path = jtmp.name
            jd_final_text = await jd_parser.parse(jd_tmp_path)
            logger.info("JD parsed: %d characters extracted", len(jd_final_text))
        except Exception as e:
            logger.error("JD parse FAILED: %s\n%s", str(e), traceback.format_exc())
            raise HTTPException(status_code=400, detail=f"Không đọc được file JD: {e}")
        finally:
            if os.path.exists(jd_tmp_path):
                os.remove(jd_tmp_path)

    # ── Create analysis + CV file records ────────────────────────
    analysis_repo = AnalysisRepository(session)
    cv_file_repo = CVFileRepository(session)

    analysis = AnalysisResult(
        user_id=user_id,
        cv_filename=cv_file.filename,
        cv_text=cv_text,
        jd_text=jd_final_text,
    )
    await analysis_repo.create(analysis)

    version = await cv_file_repo.get_next_version(user_id, cv_file.filename)
    cv_record = CVFile(
        id=file_id,
        user_id=user_id,
        analysis_id=analysis.id,
        original_filename=cv_file.filename,
        storage_key=storage_key,
        content_type=content_type,
        file_size=file_size,
        version=version,
    )
    await cv_file_repo.create(cv_record)

    await session.commit()

    logger.info(
        "Analysis created: analysis_id=%s, cv_file_id=%s (v%d), user_id=%s → dispatching to Celery",
        analysis.id, file_id, version, user_id,
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


@router.get("/{analysis_id}/stream")
async def stream_analysis(
    analysis_id: UUID,
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Stream analysis pipeline progress via Server-Sent Events (SSE)."""

    logger.info("SSE stream: analysis_id=%s, user_id=%s", analysis_id, user_id)

    # Verify ownership
    analysis_repo = AnalysisRepository(session)
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis or analysis.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy kết quả phân tích")

    # If already completed, send final event immediately
    if analysis.status.value in ("completed", "failed"):
        async def _done_stream():
            yield f"data: {json.dumps({'step': 'pipeline', 'status': analysis.status.value})}\n\n"
        return StreamingResponse(_done_stream(), media_type="text/event-stream")

    async def _event_generator():
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        channel = f"analysis:{analysis_id}"

        try:
            await pubsub.subscribe(channel)
            logger.info("SSE subscribed to channel: %s", channel)

            timeout = 120  # max seconds to stream
            start = asyncio.get_event_loop().time()
            heartbeat_interval = 5

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected: analysis_id=%s", analysis_id)
                    break

                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > timeout:
                    logger.info("SSE timeout: analysis_id=%s", analysis_id)
                    yield f"data: {json.dumps({'step': 'pipeline', 'status': 'timeout'})}\n\n"
                    break

                # Try to get a message (non-blocking with short timeout)
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=heartbeat_interval,
                    )
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    continue

                if message and message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"

                    # Check if pipeline is done
                    try:
                        event = json.loads(data)
                        if event.get("step") == "pipeline" and event.get("status") in ("done", "failed"):
                            logger.info("SSE pipeline ended: analysis_id=%s, status=%s", analysis_id, event["status"])
                            break
                    except json.JSONDecodeError:
                        pass

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis_client.close()
            logger.info("SSE cleanup done: analysis_id=%s", analysis_id)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
