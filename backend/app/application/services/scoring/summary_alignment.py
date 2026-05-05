"""Summary Alignment dimension (10% weight) — LLM judge."""
from __future__ import annotations

from typing import Any

from app.application.interfaces.ai_service import IAIService
from app.application.prompts import render_prompt
from app.domain.schemas import CVSchema, DimensionScore, JDSchema
from app.logger import get_logger

logger = get_logger("app.application.services.scoring.summary_alignment")

_MAX_RESPONSIBILITIES = 5
_MAX_MUST_HAVES = 8


def _parse_score(payload: Any) -> tuple[float | None, str]:
    if not isinstance(payload, dict):
        return None, "judge returned non-object payload"
    raw_score = payload.get("score")
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return None, "judge returned non-numeric score"
    score = max(0.0, min(100.0, score))
    reason = str(payload.get("reason") or "").strip()
    return score, reason


async def evaluate(cv: CVSchema, jd: JDSchema, ai_service: IAIService) -> DimensionScore:
    """Score whether the CV summary speaks directly to the JD.

    Args:
        cv: The candidate's structured CV.
        jd: The structured JD.
        ai_service: AI provider implementing ``generate_structured``.

    Returns:
        :class:`DimensionScore` 0..100.
    """
    summary = cv.summary.strip()
    if not summary:
        return DimensionScore(score=0.0, reason="CV has no summary section")

    prompt = render_prompt(
        "scoring_summary_alignment",
        jd_title=jd.job_title or "(unspecified)",
        jd_responsibilities="\n".join(
            f"- {r}" for r in (jd.responsibilities[:_MAX_RESPONSIBILITIES] or ["(none listed)"])
        ),
        jd_must_have_keywords=", ".join(jd.must_have_keywords[:_MAX_MUST_HAVES]) or "(none)",
        cv_summary=summary,
    )

    try:
        payload = await ai_service.generate_structured(prompt)
    except Exception as exc:
        logger.warning("summary_alignment judge failed: %s", exc, exc_info=True)
        return DimensionScore(score=0.0, reason=f"judge_failed: {type(exc).__name__}")

    score, reason = _parse_score(payload)
    if score is None:
        logger.warning("summary_alignment judge returned unparseable payload: %r", payload)
        return DimensionScore(score=0.0, reason=f"judge_failed: {reason}")
    return DimensionScore(score=score, reason=reason or "no rationale provided")
