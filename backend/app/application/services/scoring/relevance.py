"""Relevance dimension (30% weight) — LLM judge.

The LLM is given the top JD responsibilities and the top experience
bullets and asked to score 0..100 how well the candidate's *actual
work* maps to the role. Returns ``None`` on judge failure so the
aggregator can re-normalise weights.
"""
from __future__ import annotations

from typing import Any

from app.application.interfaces.ai_service import IAIService
from app.application.prompts import render_prompt
from app.domain.schemas import CVSchema, DimensionScore, JDSchema
from app.logger import get_logger

logger = get_logger("app.application.services.scoring.relevance")

_MAX_BULLETS_TO_JUDGE = 12
_MAX_RESPONSIBILITIES = 8


def _flatten_bullets(cv: CVSchema, limit: int) -> list[str]:
    """Pick the highest-signal bullets — those with action verb OR metric first."""
    primary: list[str] = []
    secondary: list[str] = []
    for entry in cv.experience:
        prefix = f"({entry.role} @ {entry.company})".strip()
        for bullet in entry.bullets:
            tagged = f"- {prefix}: {bullet.text}" if prefix.strip("()") else f"- {bullet.text}"
            if bullet.has_action_verb or bullet.has_metric:
                primary.append(tagged)
            else:
                secondary.append(tagged)
    chosen = (primary + secondary)[:limit]
    return chosen


def _parse_score(payload: Any) -> tuple[float | None, str]:
    """Coerce the LLM payload into (score, reason). Score clamped to 0..100."""
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
    """Score relevance via an LLM judge.

    Args:
        cv: The candidate's structured CV.
        jd: The structured JD (must be ``is_usable``).
        ai_service: AI provider implementing ``generate_structured``.

    Returns:
        :class:`DimensionScore` with score 0..100. On judge failure the
        score is clamped to 0 and the reason includes
        ``"judge_failed"`` so the aggregator can decide whether to
        ignore this dimension.
    """
    bullets = _flatten_bullets(cv, _MAX_BULLETS_TO_JUDGE)
    if not bullets:
        return DimensionScore(score=0.0, reason="no experience bullets to judge")

    responsibilities = jd.responsibilities[:_MAX_RESPONSIBILITIES] or ["(JD lists no responsibilities)"]

    prompt = render_prompt(
        "scoring_relevance",
        jd_responsibilities="\n".join(f"- {r}" for r in responsibilities),
        jd_title=jd.job_title or "(unspecified)",
        jd_seniority=jd.seniority,
        cv_experience_bullets="\n".join(bullets),
    )

    try:
        payload = await ai_service.generate_structured(prompt)
    except Exception as exc:
        logger.warning("relevance judge call failed: %s", exc, exc_info=True)
        return DimensionScore(score=0.0, reason=f"judge_failed: {type(exc).__name__}")

    score, reason = _parse_score(payload)
    if score is None:
        logger.warning("relevance judge returned unparseable payload: %r", payload)
        return DimensionScore(score=0.0, reason=f"judge_failed: {reason}")
    return DimensionScore(score=score, reason=reason or "no rationale provided")
