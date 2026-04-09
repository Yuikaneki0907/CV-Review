import io
import re
from typing import List, Literal
from uuid import UUID

from docx import Document
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.requests import GenerateCVRequest, ChatContextRequest, GeneratedCVUpdateRequest
from app.application.dto.responses import GeneratedCVResponse, GeneratedCVListResponse, ChatContextResponse
from app.application.use_cases.generate_cv import GenerateCVUseCase
from app.application.use_cases.chat_cv import ChatCVUseCase
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.generated_cv_repository import GeneratedCVRepository
from app.infrastructure.ai.gemini_service import GeminiService
from app.presentation.auth_routes import get_current_user_id
from app.logger import get_logger

logger = get_logger("app.presentation.generated_cv_routes")

router = APIRouter(prefix="/generated-cvs", tags=["Generated CVs"])


def _strip_markdown_inline(text: str) -> str:
    content = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", text)
    content = content.replace("**", "").replace("*", "").replace("`", "")
    return content.strip()


def _markdown_to_docx_bytes(markdown_text: str) -> bytes:
    doc = Document()

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            doc.add_paragraph("")
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            heading_level = min(len(heading_match.group(1)), 4)
            doc.add_heading(_strip_markdown_inline(heading_match.group(2)), level=heading_level)
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)$", line) or re.match(r"^\d+\.\s+(.*)$", line)
        if bullet_match:
            doc.add_paragraph(_strip_markdown_inline(bullet_match.group(1)), style="List Bullet")
            continue

        doc.add_paragraph(_strip_markdown_inline(line))

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def _get_generated_content_payload(cv_entity) -> tuple[str, str]:
    content_data = cv_entity.generated_content if isinstance(cv_entity.generated_content, dict) else {}
    output_format = content_data.get("format")

    if output_format not in {"rich_text", "markdown", "docx"}:
        if isinstance(content_data.get("markdown"), str):
            output_format = "markdown"
        elif isinstance(content_data.get("text"), str):
            output_format = "rich_text"
        else:
            output_format = "rich_text"

    content = (
        content_data.get("content")
        or content_data.get("markdown")
        or content_data.get("text")
        or ""
    )
    return output_format, content


def _build_export_filename(cv_entity, ext: str) -> str:
    job_title = (cv_entity.base_profile_data or {}).get("job_title") or "generated_cv"
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(job_title).strip().lower()).strip("_")
    if not normalized:
        normalized = "generated_cv"
    return f"{normalized[:60]}.{ext}"


@router.post("/chat", response_model=ChatContextResponse)
async def chat_cv_generation(
    req: ChatContextRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Interact with CV AI chatbot."""
    cv_repo = GeneratedCVRepository(session)
    ai_service = GeminiService()
    use_case = ChatCVUseCase(cv_repo, ai_service)

    try:
        # Convert Request DTOs to raw dicts for AI
        messages = [{"role": msg.role, "content": msg.content} for msg in req.messages]
        
        reply, cv_id = await use_case.execute(
            user_id=user_id,
            messages=messages,
            output_format=req.output_format,
        )
        if cv_id:
            await session.commit()
            
        return ChatContextResponse(
            reply=reply,
            generated_cv_id=cv_id
        )
    except Exception as e:
        await session.rollback()
        logger.error("Failed in chat interaction: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi khi giao tiếp với AI")

@router.post("/chat/stream")
async def chat_cv_generation_stream(
    req: ChatContextRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Interact with CV AI chatbot via Server-Sent Events (SSE)."""
    cv_repo = GeneratedCVRepository(session)
    ai_service = GeminiService()
    use_case = ChatCVUseCase(cv_repo, ai_service)

    try:
        messages = [{"role": msg.role, "content": msg.content} for msg in req.messages]
        stream_generator = use_case.execute_stream(
            user_id=user_id,
            messages=messages,
            output_format=req.output_format,
        )
        return StreamingResponse(
            stream_generator,
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error("Failed to start chat streaming: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi khi bắt đầu stream AI")

@router.post("/", response_model=GeneratedCVResponse)
async def generate_cv(
    req: GenerateCVRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Generate a template CV via AI and save it."""
    
    cv_repo = GeneratedCVRepository(session)
    ai_service = GeminiService()
    use_case = GenerateCVUseCase(cv_repo, ai_service)
    
    try:
        cv_entity = await use_case.execute(
            user_id=user_id,
            job_title=req.job_title,
            jd_text=req.jd_text,
            level=req.level,
            output_format=req.output_format,
        )
        await session.commit()
        
        return GeneratedCVResponse(
            id=cv_entity.id,
            status=cv_entity.status,
            target_jd_text=cv_entity.target_jd_text,
            base_profile_data=cv_entity.base_profile_data,
            generated_content=cv_entity.generated_content,
            created_at=cv_entity.created_at
        )

    except Exception as e:
        await session.rollback()
        logger.error("Failed to generate CV: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi khi AI tạo CV mẫu")


@router.get("/", response_model=List[GeneratedCVListResponse])
async def list_generated_cvs(
    limit: int = 20,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """List user's generated CVs."""
    cv_repo = GeneratedCVRepository(session)
    cvs = await cv_repo.list_by_user_id(user_id, limit, offset)
    
    return [
        GeneratedCVListResponse(
            id=c.id,
            status=c.status,
            target_jd_text=c.target_jd_text,
            job_title=c.base_profile_data.get("job_title") if c.base_profile_data else None,
            level=c.base_profile_data.get("level") if c.base_profile_data else None,
            created_at=c.created_at,
        )
        for c in cvs
    ]


@router.get("/{cv_id}", response_model=GeneratedCVResponse)
async def get_generated_cv(
    cv_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Get full generated CV."""
    cv_repo = GeneratedCVRepository(session)
    cv_entity = await cv_repo.get_by_id(cv_id)
    
    if not cv_entity or cv_entity.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy CV mẫu này")

    return GeneratedCVResponse(
        id=cv_entity.id,
        status=cv_entity.status,
        target_jd_text=cv_entity.target_jd_text,
        base_profile_data=cv_entity.base_profile_data,
        generated_content=cv_entity.generated_content,
        created_at=cv_entity.created_at
    )


@router.get("/{cv_id}/export")
async def export_generated_cv(
    cv_id: UUID,
    format: Literal["rich_text", "markdown", "docx", "text"] | None = Query(default=None),
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Export generated CV to text, markdown, or docx."""
    cv_repo = GeneratedCVRepository(session)
    cv_entity = await cv_repo.get_by_id(cv_id)

    if not cv_entity or cv_entity.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy CV mẫu này")

    stored_format, stored_content = _get_generated_content_payload(cv_entity)
    content_data = cv_entity.generated_content if isinstance(cv_entity.generated_content, dict) else {}
    export_format = format or stored_format
    if export_format == "text":
        export_format = "rich_text"

    if export_format not in {"rich_text", "markdown", "docx"}:
        raise HTTPException(status_code=400, detail="Định dạng export không hợp lệ")

    export_content = stored_content
    if export_format in {"markdown", "docx"}:
        export_content = content_data.get("markdown") or stored_content
    elif export_format == "rich_text":
        export_content = content_data.get("text") or stored_content

    if not str(export_content).strip():
        raise HTTPException(status_code=400, detail="CV không có nội dung để export")

    if export_format == "docx":
        docx_content = _markdown_to_docx_bytes(str(export_content))
        filename = _build_export_filename(cv_entity, "docx")
        return StreamingResponse(
            io.BytesIO(docx_content),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if export_format == "markdown":
        filename = _build_export_filename(cv_entity, "md")
        return Response(
            content=str(export_content),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    filename = _build_export_filename(cv_entity, "txt")
    return Response(
        content=str(export_content),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{cv_id}", response_model=GeneratedCVResponse)
async def update_generated_cv(
    cv_id: UUID,
    req: GeneratedCVUpdateRequest,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Update generated CV content after user edits in preview."""
    cv_repo = GeneratedCVRepository(session)
    cv_entity = await cv_repo.get_by_id(cv_id)

    if not cv_entity or cv_entity.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy CV mẫu này")

    existing_payload = cv_entity.generated_content if isinstance(cv_entity.generated_content, dict) else {}
    updated_payload = dict(existing_payload)
    updated_payload["format"] = req.output_format
    updated_payload["content"] = req.content

    if req.output_format in {"markdown", "docx"}:
        updated_payload["markdown"] = req.content
        updated_payload.pop("text", None)
    else:
        updated_payload["text"] = req.content
        updated_payload.pop("markdown", None)

    updated = await cv_repo.update_generated_content(
        cv_id=cv_id,
        user_id=user_id,
        generated_content=updated_payload,
    )
    if not updated:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Không tìm thấy CV mẫu này")

    await session.commit()
    return GeneratedCVResponse(
        id=updated.id,
        status=updated.status,
        target_jd_text=updated.target_jd_text,
        base_profile_data=updated.base_profile_data,
        generated_content=updated.generated_content,
        created_at=updated.created_at,
    )

@router.delete("/{cv_id}", status_code=204)
async def delete_generated_cv(
    cv_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """Soft delete generated CV."""
    cv_repo = GeneratedCVRepository(session)
    success = await cv_repo.soft_delete(cv_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy CV mẫu này")

    await session.commit()
