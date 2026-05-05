"""Suggestion generator.

Runs only when ``verdict != "PASS"`` — the aggregator decides whether
to call us. We never invent skills, employers, or metrics; the prompt
forces verbatim quoting of the candidate's existing text.
"""
from __future__ import annotations

from typing import Any

from app.application.interfaces.ai_service import IAIService
from app.application.prompts import render_prompt
from app.domain.schemas import CVSchema, GapAnalysis, JDSchema, Suggestion
from app.logger import get_logger

logger = get_logger("app.application.services.scoring.suggestions")

_MAX_BULLETS_IN_PROMPT = 12
_MAX_RESPONSIBILITIES = 6
_MAX_MUST_HAVES = 10
_MAX_SUGGESTIONS_RETURNED = 5


def _coerce_suggestions(payload: Any) -> list[Suggestion]:
    """Validate and coerce the LLM payload into ``list[Suggestion]``."""
    if not isinstance(payload, dict):
        return []
    raw = payload.get("suggestions")
    if not isinstance(raw, list):
        return []
    out: list[Suggestion] = []
    for item in raw[:_MAX_SUGGESTIONS_RETURNED]:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                Suggestion(
                    section=str(item.get("section") or "").strip() or "Unknown section",
                    issue=str(item.get("issue") or "").strip() or "no issue label",
                    current=str(item.get("current") or "").strip(),
                    suggested=str(item.get("suggested") or "").strip(),
                )
            )
        except Exception as exc:
            logger.debug("Skipped malformed suggestion item: %s", exc)
            continue
    return out


def _format_gap_summary(gap: GapAnalysis) -> str:
    critical = "\n".join(f"- CRITICAL: {item}" for item in gap.critical_missing) or "- (none)"
    improvable = "\n".join(f"- IMPROVABLE: {item}" for item in gap.improvable) or "- (none)"
    return f"{critical}\n{improvable}"


def _flatten_bullets(cv: CVSchema, limit: int) -> list[str]:
    out: list[str] = []
    for entry in cv.experience:
        prefix = f"({entry.role} @ {entry.company})".strip()
        for bullet in entry.bullets:
            tagged = (
                f"- {prefix}: {bullet.text}"
                if prefix.strip("()")
                else f"- {bullet.text}"
            )
            out.append(tagged)
            if len(out) >= limit:
                return out
    return out


async def generate(
    cv: CVSchema,
    jd: JDSchema,
    gap_analysis: GapAnalysis,
    ai_service: IAIService,
) -> list[Suggestion]:
    """Generate up to 5 concrete rewrite suggestions.

    Args:
        cv: The candidate's structured CV.
        jd: The structured JD.
        gap_analysis: The output of the aggregator's gap derivation —
            tells the LLM which gaps to prioritise.
        ai_service: AI provider implementing ``generate_structured``.

    Returns:
        List of :class:`Suggestion` objects, possibly empty if the LLM
        fails or returns malformed output.
    """
    prompt = render_prompt(
        "scoring_suggestions",
        jd_title=jd.job_title or "(unspecified)",
        jd_must_have_keywords=", ".join(jd.must_have_keywords[:_MAX_MUST_HAVES]) or "(none)",
        jd_responsibilities="\n".join(
            f"- {r}" for r in (jd.responsibilities[:_MAX_RESPONSIBILITIES] or ["(none listed)"])
        ),
        cv_summary=cv.summary or "(no summary section)",
        cv_skills=", ".join(cv.skills[:20]) or "(none listed)",
        cv_experience_bullets="\n".join(
            _flatten_bullets(cv, _MAX_BULLETS_IN_PROMPT)
        ) or "(no bullets)",
        gap_summary=_format_gap_summary(gap_analysis),
    )

    try:
        payload = await ai_service.generate_structured(prompt)
    except Exception as exc:
        logger.warning("suggestion generation failed: %s", exc, exc_info=True)
        return []

    return _coerce_suggestions(payload)
