"""CV reviser — Phase 3 entry point.

Given the previous iteration's CV markdown plus its
:class:`GapAnalysis` (and the JD), asks the LLM to fix only the
critical gaps without rewriting everything from scratch. Returns a
:class:`RevisionOutput` mirroring :class:`GenerationOutput` so the loop
can treat both calls uniformly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.interfaces.ai_service import IAIService
from app.application.prompts import render_prompt
from app.domain.schemas import GapAnalysis, JDSchema
from app.domain.schemas.cv_schema import PLACEHOLDER_PATTERN
from app.logger import get_logger

logger = get_logger("app.application.services.generation.cv_reviser")

_MIN_REVISED_CHARS = 80
_NO_DATA_PLACEHOLDER = "(không có)"


@dataclass(frozen=True)
class RevisionOutput:
    """Result of one CV-revision call."""

    content: str
    output_format: str
    placeholders_remaining: int
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.content.strip()) >= _MIN_REVISED_CHARS and not any(
            w in {"ai_returned_empty", "cv_too_short", "ai_provider_failed"}
            for w in self.warnings
        )


def _format_bullet_list(items: list[str], limit: int = 8) -> str:
    """Format a list of gap items as a bullet block for the prompt."""
    if not items:
        return _NO_DATA_PLACEHOLDER
    return "\n".join(f"- {item}" for item in items[:limit])


def _format_inline_list(items: list[str], limit: int = 12) -> str:
    """Render a list as a comma-separated string (for keyword lines)."""
    if not items:
        return _NO_DATA_PLACEHOLDER
    return ", ".join(items[:limit])


async def revise_cv(
    *,
    current_cv: str,
    gap: GapAnalysis,
    jd: JDSchema,
    ai_service: IAIService,
    job_title: str | None = None,
    level: str = "",
    missing_keywords: list[str] | None = None,
    output_format: str = "markdown",
) -> RevisionOutput:
    """Run one revision pass.

    Args:
        current_cv: Markdown body returned by the previous iteration.
        gap: ``GapAnalysis`` from the previous iteration's analyzer
            (``critical_missing`` drives the revision priorities).
        jd: Structured JD; used for ``job_title`` fallback, tools, and
            responsibilities context.
        ai_service: Concrete :class:`IAIService` implementation.
        job_title: Override for the JD-extracted title (caller usually
            forwards the request's ``job_title``).
        level: Seniority string, included for prompt context only.
        missing_keywords: Explicit list of must-have keywords still
            absent from the CV — usually pulled from
            ``KeywordReport.missing`` so the reviser can target them.
        output_format: Echoed back in the prompt and the result.

    Returns:
        :class:`RevisionOutput`.
    """
    warnings: list[str] = []

    effective_title = job_title or jd.job_title or "Không rõ"
    must_have = missing_keywords if missing_keywords is not None else list(jd.must_have_keywords)
    prompt = render_prompt(
        "cv_revision",
        job_title=effective_title,
        level=level or "Không rõ",
        missing_must_have=_format_inline_list(must_have),
        jd_tools=_format_inline_list(list(jd.tools)),
        jd_responsibilities=_format_inline_list(list(jd.responsibilities), limit=6),
        critical_gaps=_format_bullet_list(list(gap.critical_missing)),
        improvable_gaps=_format_bullet_list(list(gap.improvable)),
        current_cv=current_cv,
        output_format=output_format,
    )

    try:
        raw = await ai_service.generate_text(prompt)
    except Exception as exc:
        logger.warning("revise_cv: provider error: %s", exc, exc_info=True)
        warnings.append("ai_provider_failed")
        raw = ""

    content = (raw or "").strip()
    if not content:
        warnings.append("ai_returned_empty")
    elif len(content) < _MIN_REVISED_CHARS:
        warnings.append("cv_too_short")

    placeholders_remaining = len(PLACEHOLDER_PATTERN.findall(content))

    logger.info(
        "revise_cv: title=%r critical=%d improvable=%d missing_kw=%d placeholders=%d len=%d",
        effective_title,
        len(gap.critical_missing),
        len(gap.improvable),
        len(must_have),
        placeholders_remaining,
        len(content),
    )
    return RevisionOutput(
        content=content,
        output_format=output_format,
        placeholders_remaining=placeholders_remaining,
        warnings=warnings,
    )


__all__ = ["RevisionOutput", "revise_cv"]
