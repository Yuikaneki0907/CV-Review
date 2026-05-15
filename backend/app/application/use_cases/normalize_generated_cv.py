"""Normalize a previously imported generated CV.

The import pipeline persists a deterministic, lossy markdown extracted
from the user's uploaded PDF/DOCX. This use case takes that markdown,
runs it through :func:`normalize_imported_cv` (strict-rewrite LLM
service), and saves the cleaned-up version as a new immutable version
of the same workspace conversation.

Refusing to normalize on a non-imported CV is intentional — running the
strict-rewrite on an AI-generated CV would clobber the generator's
formatting (and there is no benefit, since the generator already emits
well-structured markdown).
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.repositories import IGeneratedCVRepository
from app.application.services.generation import (
    NormalizeOutput,
    normalize_imported_cv,
)
from app.domain.entities.generated_cv import GeneratedCV
from app.logger import get_logger

logger = get_logger("app.application.use_cases.normalize_generated_cv")


@dataclass(frozen=True)
class NormalizeGeneratedCVResult:
    """Outcome bundle returned by the use case.

    Attributes:
        cv: The new version (when ``changed=True``), or the original
            entity (when the normalize was skipped / rejected).
        changed: True iff a new version was created.
        warnings: Diagnostic codes propagated from
            :class:`NormalizeOutput`.
    """

    cv: GeneratedCV
    changed: bool
    warnings: list[str]


class NormalizeGeneratedCVUseCase:
    """Apply the strict-rewrite normalize pass to an imported CV."""

    def __init__(self, repo: IGeneratedCVRepository, ai_service: IAIService) -> None:
        self._repo = repo
        self._ai = ai_service

    async def execute(self, *, user_id: UUID, cv_id: UUID) -> NormalizeGeneratedCVResult:
        cv = await self._repo.get_by_id(cv_id)
        if not cv or cv.user_id != user_id:
            raise LookupError("CV not found")

        content_payload = cv.generated_content if isinstance(cv.generated_content, dict) else {}
        source_type = (cv.base_profile_data or {}).get("source_type") if isinstance(
            cv.base_profile_data, dict
        ) else None
        if source_type != "uploaded_cv":
            raise PermissionError("Chỉ áp dụng cho CV được import từ file")

        raw_markdown = str(
            content_payload.get("markdown")
            or content_payload.get("content")
            or ""
        ).strip()
        if not raw_markdown:
            raise ValueError("CV gốc không có nội dung markdown để chuẩn hoá")

        output: NormalizeOutput = await normalize_imported_cv(
            raw_cv=raw_markdown,
            ai_service=self._ai,
        )

        if not output.changed:
            logger.info(
                "normalize_generated_cv: skipped cv_id=%s warnings=%s",
                cv_id,
                output.warnings,
            )
            return NormalizeGeneratedCVResult(cv=cv, changed=False, warnings=output.warnings)

        # Build the new version's payload — drop the html/import-preview hints
        # so the editor falls back to the cleaned markdown.
        next_content = {
            key: value
            for key, value in content_payload.items()
            if key not in {"html", "import_preview_format"}
        }
        next_content.update(
            {
                "format": "markdown",
                "content": output.content,
                "markdown": output.content,
                "normalized_from_import": True,
            }
        )

        next_profile = dict(cv.base_profile_data or {})
        # Once normalized, the workspace no longer treats this as a raw
        # parsed draft — promote it back to a regular editable CV.
        next_profile["source_type"] = "uploaded_cv_normalized"

        new_cv = await self._repo.create_versioned(
            user_id=user_id,
            conversation_id=cv.conversation_id,
            parent_version_id=cv.id,
            target_jd_text=cv.target_jd_text,
            base_profile_data=next_profile,
            generated_content=next_content,
            status=cv.status,
        )

        logger.info(
            "normalize_generated_cv: cv_id=%s → new_version_id=%s len=%d",
            cv_id,
            new_cv.id,
            len(output.content),
        )
        return NormalizeGeneratedCVResult(cv=new_cv, changed=True, warnings=output.warnings)


__all__ = ["NormalizeGeneratedCVResult", "NormalizeGeneratedCVUseCase"]
