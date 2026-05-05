"""Analysis routes — thin orchestration over the Phase 1 analyzer.

Route handlers MUST NOT contain scoring or extraction logic. They only:
- validate request shape
- call ``extract_document_text`` for any uploaded file
- create the AnalysisResult row
- dispatch the Celery task (or stream the use case inline for SSE)

All scoring lives in ``application.services.scoring.score_cv``.
"""
from __future__ import annotations

import asyncio
import json
from io import BytesIO
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.requests import AnalysisRequest
from app.application.dto.responses import (
    AnalysisListResponse,
    AnalysisResponse,
    DiffSegmentResponse,
    HallucinationWarningResponse,
    ScoreResponse,
    SkillResponse,
)
from app.application.exceptions import DocumentExtractionError
from app.application.services.shared import extract_document_text
from app.application.use_cases.analyze_cv import AnalyzeCVUseCase
from app.config import get_settings
from app.domain.entities.analysis_result import AnalysisResult
from app.infrastructure.ai import ai_service_factory
from app.infrastructure.celery.tasks import run_analysis_task
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.cv_file_repository import CVFileRepository
from app.infrastructure.database.repositories.generated_cv_repository import GeneratedCVRepository
from app.infrastructure.database.session import get_db_session
from app.infrastructure.file_parsers.upload_validation import read_and_validate_upload
from app.infrastructure.storage.minio_storage import MinioFileStorage
from app.logger import get_logger
from app.presentation.dependencies import get_current_user_id

logger = get_logger("app.presentation.analysis")

router = APIRouter(prefix="/analysis", tags=["Analysis"])

_file_storage: MinioFileStorage | None = None


def _get_file_storage() -> MinioFileStorage:
    """Lazy MinIO client — created once per process."""
    global _file_storage
    if _file_storage is None:
        _file_storage = MinioFileStorage()
    return _file_storage


def _heuristic_document_type(text: str) -> str:
    """Cheap CV-vs-JD classifier used as a fallback when AI classification fails."""
    normalized = (text or "").lower()
    cv_hits = sum(
        token in normalized
        for token in [
            "curriculum vitae",
            "resume",
            "education",
            "work experience",
            "experience",
            "skills",
            "projects",
            "email",
            "phone",
            "linkedin",
        ]
    )
    jd_hits = sum(
        token in normalized
        for token in [
            "job description",
            "responsibilities",
            "requirements",
            "qualifications",
            "we are looking",
            "benefits",
            "salary",
            "candidate",
            "apply",
            "role",
        ]
    )
    if jd_hits >= cv_hits + 2:
        return "job_description"
    if cv_hits >= jd_hits + 2:
        return "cv"
    return "other"


async def _classify_uploaded_document(text: str, filename: str) -> dict:
    """Classify an upload as CV / JD / other.

    Tries the AI service first; falls back to the keyword-count heuristic
    when the AI is unavailable or returns a bad payload.
    """
    try:
        ai_service = ai_service_factory()
        result = await ai_service.classify_document(text, filename)
        document_type = result.get("document_type")
        if document_type in {"cv", "job_description", "other"}:
            return result
    except Exception as exc:
        logger.warning("Document classification failed for %s: %s", filename, exc)

    document_type = _heuristic_document_type(text)
    return {
        "document_type": document_type,
        "confidence": 0.45,
        "reason": "Phân loại bằng heuristic vì AI không trả kết quả hợp lệ.",
    }


async def _read_upload_text(
    upload: UploadFile,
    allowed_types: set[str],
    *,
    max_size_mb: int,
    error_label: str,
) -> tuple[bytes, str, str]:
    """Read + validate + extract text from an uploaded file.

    Returns:
        (file_bytes, filename, extracted_text)

    Raises:
        HTTPException(400) on validation or extraction failure.
    """
    file_bytes, meta = await read_and_validate_upload(
        upload,
        allowed_types=allowed_types,
        max_size_mb=max_size_mb,
        detail=error_label,
    )
    try:
        extracted = await extract_document_text(file_bytes, meta.filename)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=400, detail=f"Không đọc được file: {exc}") from exc

    if extracted.extraction_quality == "low":
        logger.warning(
            "Low-quality extraction: filename=%s warnings=%s",
            meta.filename,
            extracted.warnings,
        )

    return file_bytes, meta.filename, extracted.text


def _build_generated_analysis_meta(cv_entity, cv_text: str) -> dict:
    """Provenance metadata when analyze runs against a generated CV.

    The analyzer's pre-flight short-circuit reads ``source`` to know
    template-only CVs originated from feature 1 (the generator), so
    the message can be more specific in the response.
    """
    content_data = cv_entity.generated_content if isinstance(cv_entity.generated_content, dict) else {}
    base_profile = cv_entity.base_profile_data if isinstance(cv_entity.base_profile_data, dict) else {}
    generation_mode = (
        content_data.get("generation_mode")
        or base_profile.get("generation_mode")
        or "unknown"
    )
    target_jd = (cv_entity.target_jd_text or "").strip()
    if target_jd == "Được cung cấp qua chat":
        target_jd = ""
    return {
        "source": "generated_cv",
        "generated_cv_id": str(cv_entity.id),
        "generation_mode": generation_mode,
        "source_target_jd_text": target_jd,
    }


# ─────────────────────────────────────────────────────────────────
# POST /analysis/
# ─────────────────────────────────────────────────────────────────
@router.post("/", response_model=AnalysisResponse, status_code=201)
async def create_analysis(
    cv_file: UploadFile = File(...),
    jd_text: str = Form(""),
    jd_file: UploadFile | None = File(None),
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResponse:
    """Upload CV + paste-or-upload JD; dispatch Celery analysis."""
    settings = get_settings()

    if not jd_text.strip() and (jd_file is None or not jd_file.filename):
        raise HTTPException(
            status_code=400,
            detail="Cần nhập Job Description (dán text hoặc upload file)",
        )
    if not cv_file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    cv_bytes, cv_filename, cv_text = await _read_upload_text(
        cv_file,
        allowed_types={"pdf", "docx"},
        max_size_mb=settings.MAX_FILE_SIZE_MB,
        error_label="Chỉ hỗ trợ file CV định dạng PDF hoặc DOCX",
    )

    jd_final_text = jd_text.strip()
    if jd_file is not None and jd_file.filename:
        _, _, jd_final_text = await _read_upload_text(
            jd_file,
            allowed_types={"pdf", "docx", "txt", "md"},
            max_size_mb=settings.MAX_FILE_SIZE_MB,
            error_label="JD file: chỉ hỗ trợ PDF, DOCX, TXT hoặc MD",
        )

    # MinIO upload of the raw CV bytes (storage for audit trail).
    storage = _get_file_storage()
    file_id = uuid4()
    ext = "." + cv_filename.rsplit(".", 1)[-1].lower()
    storage_key = f"{user_id}/{file_id}{ext}"
    storage.upload(
        bucket=settings.MINIO_BUCKET_NAME,
        key=storage_key,
        data=BytesIO(cv_bytes),
        length=len(cv_bytes),
        content_type=cv_file.content_type or "application/octet-stream",
    )

    analysis_repo = AnalysisRepository(session)
    cv_file_repo = CVFileRepository(session)

    analysis = AnalysisResult(
        user_id=user_id,
        cv_filename=cv_filename,
        cv_text=cv_text,
        jd_text=jd_final_text,
    )
    await analysis_repo.create(analysis)
    await cv_file_repo.create_with_next_version(
        file_id=file_id,
        user_id=user_id,
        analysis_id=analysis.id,
        original_filename=cv_filename,
        storage_key=storage_key,
        content_type=cv_file.content_type or "application/octet-stream",
        file_size=len(cv_bytes),
    )
    await session.commit()

    run_analysis_task.delay(str(analysis.id))
    return _to_response(analysis)


# ─────────────────────────────────────────────────────────────────
# GET /analysis/
# ─────────────────────────────────────────────────────────────────
@router.get("/", response_model=List[AnalysisListResponse])
async def list_analyses(
    limit: int = 20,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[AnalysisListResponse]:
    """List user's analysis history."""
    analysis_repo = AnalysisRepository(session)
    analyses = await analysis_repo.get_by_user_id(user_id, limit, offset)
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


# ─────────────────────────────────────────────────────────────────
# POST /analysis/from-generated-cv/{cv_id}
# ─────────────────────────────────────────────────────────────────
@router.post("/from-generated-cv/{cv_id}", response_model=AnalysisResponse, status_code=201)
async def create_analysis_from_generated_cv(
    cv_id: UUID,
    req: AnalysisRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResponse:
    """Run analysis directly against a generated CV (no file upload)."""
    jd_final_text = req.jd_text.strip()
    if not jd_final_text:
        raise HTTPException(status_code=400, detail="Cần nhập Job Description để phân tích")

    generated_repo = GeneratedCVRepository(session)
    cv_entity = await generated_repo.get_by_id(cv_id)
    if not cv_entity or cv_entity.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy CV đã tạo")

    content_data = cv_entity.generated_content if isinstance(cv_entity.generated_content, dict) else {}
    cv_text = (
        content_data.get("markdown")
        or content_data.get("content")
        or content_data.get("text")
        or ""
    ).strip()
    if not cv_text:
        raise HTTPException(status_code=400, detail="CV đã tạo không có nội dung để phân tích")

    title = (cv_entity.base_profile_data or {}).get("job_title") or "CV đã tạo"
    analysis_repo = AnalysisRepository(session)
    analysis = AnalysisResult(
        user_id=user_id,
        cv_filename=f"{title} (generated)",
        cv_text=cv_text,
        jd_text=jd_final_text,
        analysis_meta=_build_generated_analysis_meta(cv_entity, cv_text),
    )
    await analysis_repo.create(analysis)
    await session.commit()
    run_analysis_task.delay(str(analysis.id))
    return _to_response(analysis)


# ─────────────────────────────────────────────────────────────────
# POST /analysis/from-generated-cv/{cv_id}/upload
# ─────────────────────────────────────────────────────────────────
@router.post(
    "/from-generated-cv/{cv_id}/upload",
    response_model=AnalysisResponse,
    status_code=201,
)
async def create_analysis_from_generated_cv_upload(
    cv_id: UUID,
    jd_text: str = Form(""),
    jd_file: UploadFile | None = File(None),
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResponse:
    """As above, but accepts a JD file upload too."""
    settings = get_settings()
    jd_final_text = jd_text.strip()
    if not jd_final_text and (jd_file is None or not jd_file.filename):
        raise HTTPException(
            status_code=400,
            detail="Cần nhập hoặc đính kèm Job Description để phân tích",
        )

    generated_repo = GeneratedCVRepository(session)
    cv_entity = await generated_repo.get_by_id(cv_id)
    if not cv_entity or cv_entity.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy CV đã tạo")

    content_data = cv_entity.generated_content if isinstance(cv_entity.generated_content, dict) else {}
    cv_text = (
        content_data.get("markdown")
        or content_data.get("content")
        or content_data.get("text")
        or ""
    ).strip()
    if not cv_text:
        raise HTTPException(status_code=400, detail="CV đã tạo không có nội dung để phân tích")

    if jd_file is not None and jd_file.filename:
        _, jd_filename, uploaded_text = await _read_upload_text(
            jd_file,
            allowed_types={"pdf", "docx", "txt", "md"},
            max_size_mb=settings.MAX_FILE_SIZE_MB,
            error_label="Tài liệu đính kèm: chỉ hỗ trợ PDF, DOCX, TXT hoặc MD",
        )
        if not uploaded_text.strip():
            raise HTTPException(
                status_code=400, detail="Tài liệu đính kèm không có nội dung để phân tích"
            )

        classification = await _classify_uploaded_document(uploaded_text, jd_filename)
        document_type = classification.get("document_type")
        if document_type == "job_description":
            jd_final_text = uploaded_text.strip()
        elif jd_final_text:
            logger.info(
                "Attachment %s is not a JD (%s); using pasted JD text instead",
                jd_filename,
                document_type,
            )
        elif document_type == "cv":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Tài liệu đính kèm có vẻ là CV, không phải Job Description. "
                    "Hãy gửi JD/job posting để phân tích CV hiện tại."
                ),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Chưa xác định được tài liệu đính kèm là JD hay CV. "
                    "Hãy dán nội dung JD hoặc gửi file job rõ hơn."
                ),
            )

    if not jd_final_text.strip():
        raise HTTPException(status_code=400, detail="JD không có nội dung để phân tích")

    title = (cv_entity.base_profile_data or {}).get("job_title") or "CV đã tạo"
    analysis_repo = AnalysisRepository(session)
    analysis = AnalysisResult(
        user_id=user_id,
        cv_filename=f"{title} (generated)",
        cv_text=cv_text,
        jd_text=jd_final_text,
        analysis_meta=_build_generated_analysis_meta(cv_entity, cv_text),
    )
    await analysis_repo.create(analysis)
    await session.commit()
    run_analysis_task.delay(str(analysis.id))
    return _to_response(analysis)


# ─────────────────────────────────────────────────────────────────
# GET /analysis/{analysis_id}
# ─────────────────────────────────────────────────────────────────
@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisResponse:
    """Get full analysis details."""
    analysis_repo = AnalysisRepository(session)
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis or analysis.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy kết quả phân tích")
    return _to_response(analysis)


# ─────────────────────────────────────────────────────────────────
# DELETE /analysis/{analysis_id}
# ─────────────────────────────────────────────────────────────────
@router.delete("/{analysis_id}", status_code=204, response_model=None)
async def delete_analysis(
    analysis_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Soft-delete an analysis."""
    analysis_repo = AnalysisRepository(session)
    try:
        success = await analysis_repo.soft_delete(analysis_id, user_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy kết quả phân tích hoặc đã bị xóa"
            )
        await session.commit()
        return None
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        logger.error(
            "Delete analysis failed: analysis_id=%s user_id=%s: %s",
            analysis_id,
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Không thể xóa bản phân tích. Vui lòng thử lại."
        )


# ─────────────────────────────────────────────────────────────────
# POST /analysis/chat-analyze/stream
# ─────────────────────────────────────────────────────────────────
@router.post("/chat-analyze/stream")
async def chat_analyze_stream(
    cv_file: UploadFile = File(...),
    jd_text: str = Form(""),
    jd_file: UploadFile | None = File(None),
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Upload + analyze + stream events inline (used by the chatbot UI).

    The route prepares the AnalysisResult row, then delegates streaming
    to :meth:`AnalyzeCVUseCase.execute_stream` — no inline pipeline.
    """
    settings = get_settings()

    if not jd_text.strip() and (jd_file is None or not jd_file.filename):
        raise HTTPException(
            status_code=400, detail="Cần nhập Job Description (dán text hoặc upload file)"
        )
    if not cv_file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    cv_bytes, cv_filename, cv_text = await _read_upload_text(
        cv_file,
        allowed_types={"pdf", "docx"},
        max_size_mb=settings.MAX_FILE_SIZE_MB,
        error_label="Chỉ hỗ trợ file CV định dạng PDF hoặc DOCX",
    )

    jd_final_text = jd_text.strip()
    if jd_file is not None and jd_file.filename:
        _, _, jd_final_text = await _read_upload_text(
            jd_file,
            allowed_types={"pdf", "docx", "txt", "md"},
            max_size_mb=settings.MAX_FILE_SIZE_MB,
            error_label="JD file: chỉ hỗ trợ PDF, DOCX, TXT hoặc MD",
        )

    storage = _get_file_storage()
    file_id = uuid4()
    ext = "." + cv_filename.rsplit(".", 1)[-1].lower()
    storage_key = f"{user_id}/{file_id}{ext}"
    storage.upload(
        bucket=settings.MINIO_BUCKET_NAME,
        key=storage_key,
        data=BytesIO(cv_bytes),
        length=len(cv_bytes),
        content_type=cv_file.content_type or "application/octet-stream",
    )

    analysis_repo = AnalysisRepository(session)
    cv_file_repo = CVFileRepository(session)

    analysis = AnalysisResult(
        user_id=user_id,
        cv_filename=cv_filename,
        cv_text=cv_text,
        jd_text=jd_final_text,
    )
    await analysis_repo.create(analysis)
    await cv_file_repo.create_with_next_version(
        file_id=file_id,
        user_id=user_id,
        analysis_id=analysis.id,
        original_filename=cv_filename,
        storage_key=storage_key,
        content_type=cv_file.content_type or "application/octet-stream",
        file_size=len(cv_bytes),
    )
    await session.commit()

    ai_service = ai_service_factory()
    use_case = AnalyzeCVUseCase(analysis_repo, ai_service)

    async def _stream() -> "asyncio.AsyncGenerator[str, None]":
        async for chunk in use_case.execute_stream(analysis.id):
            yield chunk

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────
# GET /analysis/{analysis_id}/stream
# ─────────────────────────────────────────────────────────────────
@router.get("/{analysis_id}/stream")
async def stream_analysis(
    analysis_id: UUID,
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """SSE proxy that relays Celery pub/sub events to the browser."""
    analysis_repo = AnalysisRepository(session)
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis or analysis.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy kết quả phân tích")

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
            timeout = 120
            start = asyncio.get_event_loop().time()
            heartbeat_interval = 5

            while True:
                if await request.is_disconnected():
                    break
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > timeout:
                    yield f"data: {json.dumps({'step': 'pipeline', 'status': 'timeout'})}\n\n"
                    break
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=heartbeat_interval,
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if message and message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"
                    try:
                        event = json.loads(data)
                        if event.get("step") in ("done", "pipeline") and event.get(
                            "status"
                        ) in ("done", "failed"):
                            break
                    except json.JSONDecodeError:
                        pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis_client.close()

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────
# Response builder
# ─────────────────────────────────────────────────────────────────
def _to_response(analysis: AnalysisResult) -> AnalysisResponse:
    """Map an AnalysisResult entity to the API response.

    The new ``score_breakdown`` field carries the Phase 1 schema
    (verdict / dimension_scores / gap_analysis / keyword_report /
    suggestions). Legacy fields (rewritten_cv / diff_segments /
    hallucination_warnings / jd_evaluation / interview_questions /
    salary_negotiation) are no longer populated by the analyzer; they
    surface as ``None`` and frontend panels degrade gracefully.
    """
    score = None
    if analysis.score:
        score = ScoreResponse(
            overall=analysis.score.overall,
            skills_score=analysis.score.skills_score,
            experience_score=analysis.score.experience_score,
            tools_score=analysis.score.tools_score,
        )

    matched = missing = extra = None
    if analysis.skill_analysis:
        matched = [
            SkillResponse(name=s.name, category=s.category, proficiency=s.proficiency, reason=s.reason)
            for s in analysis.skill_analysis.matched_skills
        ]
        missing = [
            SkillResponse(name=s.name, category=s.category, proficiency=s.proficiency, reason=s.reason)
            for s in analysis.skill_analysis.missing_skills
        ]
        extra = [
            SkillResponse(name=s.name, category=s.category, proficiency=s.proficiency, reason=s.reason)
            for s in analysis.skill_analysis.extra_skills
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
        section_diffs=None,
        hallucination_warnings=warnings,
        jd_evaluation=analysis.jd_evaluation,
        interview_questions=analysis.interview_questions,
        salary_negotiation=analysis.salary_negotiation,
        analysis_meta=analysis.analysis_meta,
        score_breakdown=analysis.score_breakdown,
    )
