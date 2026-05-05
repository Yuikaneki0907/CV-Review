"""GenerateCVUseCase — Phase 2 entry point.

Thin orchestrator: render JD + profile through the generation service,
persist the result with provenance. Prompt assembly and post-processing
live in :mod:`app.application.services.generation`.
"""
from __future__ import annotations

import re
from typing import Mapping
from uuid import UUID

from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.repositories import IGeneratedCVRepository
from app.application.services.generation import GenerationOutput, generate_cv
from app.domain.entities.generated_cv import GeneratedCV
from app.logger import get_logger

logger = get_logger("app.application.use_cases.generate_cv")

_MIN_GENERATED_CV_CHARS = 80
_CV_SECTION_KEYWORDS = (
    "summary",
    "objective",
    "skills",
    "kỹ năng",
    "kinh nghiệm",
    "experience",
    "education",
    "học vấn",
    "projects",
    "dự án",
)


def _looks_like_cv_template(value: str) -> bool:
    """Heuristic guard against AI responses that aren't CVs at all."""
    text = (value or "").strip()
    if len(re.sub(r"\s+", " ", text)) < _MIN_GENERATED_CV_CHARS:
        return False
    lower_text = text.lower()
    heading_count = len(re.findall(r"(?m)^#{1,3}\s+\S+", text))
    return heading_count >= 2 and any(
        keyword in lower_text for keyword in _CV_SECTION_KEYWORDS
    )


class GenerateCVUseCase:
    """Orchestrator for the CV generation feature."""

    def __init__(
        self,
        cv_repo: IGeneratedCVRepository,
        ai_service: IAIService,
    ):
        self._cv_repo = cv_repo
        self._ai_service = ai_service

    async def execute(
        self,
        user_id: UUID,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
        user_profile: Mapping[str, object] | None = None,
    ) -> GeneratedCV:
        """Generate one CV and save it.

        ``user_profile`` is opt-in: when ``None`` the generator runs in
        template-only mode and ``base_profile_data['profile_fallback']``
        is omitted. When a dict is supplied (even empty) it is stored
        verbatim so downstream consumers can distinguish "no profile
        was attempted" from "we tried but had no fields".
        """

        logger.info(
            "Generating CV for user_id=%s, job_title=%s, level=%s, output_format=%s, has_profile=%s",
            user_id,
            job_title,
            level,
            output_format,
            user_profile is not None,
        )

        result: GenerationOutput = await generate_cv(
            job_title=job_title,
            jd_text=jd_text,
            level=level,
            ai_service=self._ai_service,
            output_format=output_format,
            user_profile=user_profile,
        )

        if not _looks_like_cv_template(result.content):
            logger.warning(
                "Rejected generated CV before save: user_id=%s, jd_len=%d, content_len=%d, warnings=%s",
                user_id,
                len(jd_text or ""),
                len(result.content),
                result.warnings,
            )
            raise ValueError("AI returned invalid generated CV content")

        generated_content = {
            "content": result.content,
            "format": output_format,
            "markdown": result.content,
            "generation_mode": result.generation_mode,
            "placeholder_count": result.placeholders_remaining,
            "source_jd_text": jd_text,
            "candidate_facts": dict(user_profile) if user_profile else {},
        }

        base_profile_data: dict = {
            "job_title": job_title,
            "level": level,
            "generation_mode": result.generation_mode,
            "candidate_facts": dict(user_profile) if user_profile else {},
        }
        if user_profile is not None:
            base_profile_data["profile_fallback"] = dict(user_profile)

        cv_entity = GeneratedCV(
            user_id=user_id,
            target_jd_text=jd_text,
            base_profile_data=base_profile_data,
            generated_content=generated_content,
            status="completed",
        )

        saved_cv = await self._cv_repo.create(cv_entity)
        logger.info(
            "Generated CV saved: cv_id=%s mode=%s placeholders=%d",
            saved_cv.id,
            result.generation_mode,
            result.placeholders_remaining,
        )
        return saved_cv
