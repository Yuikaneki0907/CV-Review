import os
import re
from uuid import UUID

from app.domain.entities.generated_cv import GeneratedCV
from app.application.interfaces.repositories import IGeneratedCVRepository


def _derive_job_title(filename: str) -> str:
    base_name = os.path.splitext(filename or "")[0]
    normalized = re.sub(r"[_\-]+", " ", base_name).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return "CV Imported"
    return normalized[:80]


class ImportGeneratedCVUseCase:
    """Create an editable generated CV from an uploaded CV file."""

    def __init__(self, cv_repo: IGeneratedCVRepository):
        self._cv_repo = cv_repo

    async def execute(
        self,
        *,
        user_id: UUID,
        filename: str,
        parsed_content: str,
        preview_html: str = "",
    ) -> GeneratedCV:
        content = (parsed_content or "").strip()
        if not content:
            raise ValueError("Không trích xuất được nội dung CV từ file upload")

        job_title = _derive_job_title(filename)
        initial_message = f"Đã import CV từ file `{filename}`. Bạn có thể chỉnh sửa trực tiếp hoặc yêu cầu AI cập nhật tiếp."

        cv_entity = GeneratedCV(
            user_id=user_id,
            target_jd_text="",
            base_profile_data={
                "job_title": job_title,
                "level": "Imported",
                "source_filename": filename,
                "source_type": "uploaded_cv",
            },
            generated_content={
                "format": "markdown",
                "content": content,
                "markdown": content,
                "html": preview_html.strip() if preview_html else "",
                "import_preview_format": "html" if preview_html.strip() else "markdown",
                "source_filename": filename,
                "chat_history": [
                    {"role": "assistant", "content": initial_message},
                ],
            },
            status="completed",
        )

        return await self._cv_repo.create(cv_entity)
