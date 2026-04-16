import re
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.repositories import IGeneratedCVRepository
from app.domain.entities.generated_cv import GeneratedCV


def _normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _extract_markdown_content(cv: GeneratedCV) -> str:
    content_data = cv.generated_content if isinstance(cv.generated_content, dict) else {}
    return (
        content_data.get("markdown")
        or content_data.get("content")
        or content_data.get("text")
        or ""
    )


def _find_section_bounds(markdown: str, heading: str) -> tuple[int, int, int] | None:
    heading_pattern = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
    target = _normalize_heading(heading)
    matches = list(heading_pattern.finditer(markdown))

    for index, match in enumerate(matches):
        if _normalize_heading(match.group(2)) != target:
            continue

        level = len(match.group(1))
        start = match.start()
        body_start = match.end()
        end = len(markdown)

        for next_match in matches[index + 1 :]:
            if len(next_match.group(1)) <= level:
                end = next_match.start()
                break

        return start, body_start, end

    return None


def _ensure_leading_newline(value: str) -> str:
    if not value:
        return value
    return value if value.startswith("\n") else f"\n{value}"


def apply_markdown_operations(markdown: str, operations: List[Dict]) -> str:
    updated = markdown

    for op in operations:
        op_type = (op.get("type") or "").strip()
        if not op_type:
            continue

        if op_type == "replace_text":
            target = op.get("target") or ""
            if target and target in updated:
                updated = updated.replace(target, op.get("content") or "", 1)
            continue

        if op_type == "remove_text":
            target = op.get("target") or ""
            if target:
                updated = updated.replace(target, "", 1)
            continue

        if op_type == "insert_after_text":
            target = op.get("target") or ""
            content = op.get("content") or ""
            if target and target in updated and content:
                updated = updated.replace(target, f"{target}{content}", 1)
            continue

        heading = op.get("heading") or ""
        if not heading:
            continue

        bounds = _find_section_bounds(updated, heading)
        if not bounds:
            continue

        section_start, body_start, section_end = bounds
        section_header = updated[section_start:body_start]
        section_body = updated[body_start:section_end]

        if op_type == "replace_section_body":
            replacement = op.get("content") or ""
            replacement = replacement.strip("\n")
            new_section = f"{section_header}\n{replacement}\n"
            updated = f"{updated[:section_start]}{new_section}{updated[section_end:]}"
            continue

        if op_type == "append_to_section":
            content = (op.get("content") or "").rstrip()
            if not content:
                continue
            new_body = section_body.rstrip() + _ensure_leading_newline(content) + "\n"
            updated = f"{updated[:body_start]}{new_body}{updated[section_end:]}"

    return updated.strip() + "\n"


class EditGeneratedCVUseCase:
    """Apply targeted CV edit operations and persist a new immutable version."""

    def __init__(self, repo: IGeneratedCVRepository, ai_service: IAIService):
        self._repo = repo
        self._ai = ai_service

    async def execute(
        self,
        *,
        user_id: UUID,
        current_cv: GeneratedCV,
        messages: List[Dict[str, str]],
        output_format: str = "markdown",
    ) -> Tuple[str, Optional[GeneratedCV], str]:
        current_content = _extract_markdown_content(current_cv).strip()
        if not current_content:
            return "Mình chưa có nội dung CV hiện tại để chỉnh sửa.", None, ""

        plan = await self._ai.plan_cv_edits(
            messages=messages,
            current_cv=current_content,
            output_format=output_format,
        )

        assistant_reply = (plan.get("assistant_reply") or "").strip()
        operations = plan.get("operations") or []

        if not isinstance(operations, list):
            operations = []

        if not operations:
            return assistant_reply or "Mình cần thêm thông tin để chỉnh sửa chính xác hơn.", None, current_content

        next_content = apply_markdown_operations(current_content, operations).strip()
        if not next_content or next_content == current_content:
            return assistant_reply or "Mình chưa tìm thấy thay đổi cụ thể để áp vào CV hiện tại.", None, current_content

        next_version = await self._repo.get_next_version(user_id, current_cv.conversation_id)
        generated_payload = {
            "format": output_format,
            "content": next_content,
            "markdown": next_content,
            "chat_history": messages + [{"role": "assistant", "content": assistant_reply or "Đã cập nhật CV theo yêu cầu."}],
        }
        new_cv = GeneratedCV(
            user_id=user_id,
            conversation_id=current_cv.conversation_id,
            version=next_version,
            parent_version_id=current_cv.id,
            target_jd_text=current_cv.target_jd_text,
            base_profile_data=current_cv.base_profile_data,
            generated_content=generated_payload,
            status="completed",
        )
        await self._repo.create(new_cv)
        return assistant_reply or "Đã cập nhật CV theo yêu cầu và lưu thành phiên bản mới.", new_cv, next_content
