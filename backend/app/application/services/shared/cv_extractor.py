"""CV → CVSchema.

LLM extracts the structure; deterministic post-processing tags each
bullet with ``has_action_verb`` / ``has_metric`` so the achievement-
quality scorer (Phase 1) is pure-Python.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from app.application.interfaces.ai_service import IAIService
from app.application.prompts import render_prompt
from app.application.services.shared.skill_normalisation import normalize_skill_tokens
from app.domain.schemas import CVBullet, CVExperienceEntry, CVSchema
from app.domain.schemas.cv_schema import PLACEHOLDER_PATTERN
from app.logger import get_logger

logger = get_logger("app.application.services.shared.cv_extractor")

PlaceholderHandling = Literal["strip", "keep", "reject"]
_MIN_CV_CHARS = 80
_PLACEHOLDER_REJECT_THRESHOLD = 5

# Action verbs that signal an achievement-shaped bullet. English + Vietnamese.
# Match at the start of a bullet (optionally after a leading dash / bullet glyph).
_ACTION_VERBS: tuple[str, ...] = (
    "built",
    "designed",
    "developed",
    "implemented",
    "led",
    "managed",
    "optimised",
    "optimized",
    "improved",
    "reduced",
    "increased",
    "delivered",
    "launched",
    "deployed",
    "migrated",
    "owned",
    "shipped",
    "architected",
    "scaled",
    "automated",
    # Vietnamese
    "phát triển",
    "xây dựng",
    "triển khai",
    "thiết kế",
    "tối ưu",
    "quản lý",
    "dẫn dắt",
    "cải thiện",
    "giảm",
    "tăng",
)
_ACTION_VERB_RE = re.compile(
    r"^[\s\-\*•]*("
    + "|".join(re.escape(v) for v in _ACTION_VERBS)
    + r")\b",
    flags=re.IGNORECASE,
)
# Quantifiable result: digits + (% | x | k | m | b | bn | "users" | "ms" | "s" | …).
_METRIC_RE = re.compile(
    r"\b\d[\d.,]*\s*(?:%|x|k|m|b|bn|users?|requests?|ms|s\b|hours?|days?|months?|years?)?",
    flags=re.IGNORECASE,
)
# Concrete candidate facts that indicate "this is a real person, not a template".
_CANDIDATE_FACT_PATTERNS = (
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),  # email
    re.compile(r"(?i)github\.com/[\w-]+"),
    re.compile(r"(?i)linkedin\.com/in/[\w-]+"),
    re.compile(r"(?:\+?84|0)\d[\d\s.\-]{7,12}\d"),  # VN phone
)


def _has_action_verb(text: str) -> bool:
    """Deterministic check — does the bullet open with an action verb?"""
    return bool(_ACTION_VERB_RE.search(text))


def _has_metric(text: str) -> bool:
    """Deterministic check — does the bullet contain a number with units?

    Bare numbers (e.g. "joined in 2024") would slip through, but combined
    with the unit suffix pattern the false-positive rate is low for the
    bullets we care about scoring.
    """
    # Require at least one digit AND avoid pure year-only matches.
    match = _METRIC_RE.search(text)
    if not match:
        return False
    matched = match.group(0)
    # If the match is a bare 4-digit year with no unit, skip it.
    if re.fullmatch(r"\d{4}", matched.strip()):
        return False
    return True


def _detect_candidate_facts(raw_text: str) -> bool:
    """True if the CV body contains any concrete identifying evidence."""
    if not raw_text:
        return False
    for pattern in _CANDIDATE_FACT_PATTERNS:
        if pattern.search(raw_text):
            return True
    return False


def _strip_placeholders(text: str) -> str:
    """Replace placeholders with empty string before sending to LLM."""
    return PLACEHOLDER_PATTERN.sub("", text)


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _coerce_experience(raw: Any) -> list[CVExperienceEntry]:
    """Build experience entries with deterministic bullet tagging."""
    if not isinstance(raw, list):
        return []
    entries: list[CVExperienceEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        bullets_raw = item.get("bullets") or []
        if not isinstance(bullets_raw, list):
            bullets_raw = [bullets_raw]
        bullets: list[CVBullet] = []
        for bullet in bullets_raw:
            text = str(bullet).strip()
            if not text:
                continue
            bullets.append(
                CVBullet(
                    text=text,
                    has_action_verb=_has_action_verb(text),
                    has_metric=_has_metric(text),
                    keywords_hit=[],
                )
            )
        entries.append(
            CVExperienceEntry(
                role=str(item.get("role") or "").strip(),
                company=str(item.get("company") or "").strip(),
                period=str(item.get("period") or "").strip(),
                bullets=bullets,
            )
        )
    return entries


async def extract_cv(
    cv_text: str,
    ai_service: IAIService,
    *,
    placeholder_handling: PlaceholderHandling = "strip",
) -> CVSchema:
    """Extract a structured :class:`CVSchema` from raw CV text.

    Args:
        cv_text: Raw CV body (markdown or plaintext).
        ai_service: Concrete :class:`IAIService` implementation.
        placeholder_handling:
            * ``"strip"`` — replace ``[...]`` / ``<...>`` placeholders with
              empty string before sending to the LLM (default; what
              Phase 1 wants).
            * ``"keep"`` — leave them in place (debugging).
            * ``"reject"`` — short-circuit to ``CVSchema.empty`` when the
              placeholder count is above the configured threshold.

    Returns:
        A :class:`CVSchema`. On any failure returns
        ``CVSchema.empty(reason=...)`` with the original text preserved.
    """
    raw = (cv_text or "").strip()
    placeholder_count = len(PLACEHOLDER_PATTERN.findall(raw))

    if len(raw) < _MIN_CV_CHARS:
        return CVSchema.empty("cv_too_short", raw_text=raw)

    if (
        placeholder_handling == "reject"
        and placeholder_count > _PLACEHOLDER_REJECT_THRESHOLD
    ):
        return CVSchema(
            raw_text=raw,
            placeholders_remaining=placeholder_count,
            candidate_facts_present=False,
            extraction_warnings=["too_many_placeholders"],
        )

    cleaned = _strip_placeholders(raw) if placeholder_handling == "strip" else raw
    prompt = render_prompt("cv_extraction", cv_text=cleaned)

    try:
        payload = await ai_service.generate_structured(prompt, expect_list=False)
    except Exception as exc:
        logger.warning("extract_cv: ai_service error: %s", exc, exc_info=True)
        return CVSchema(
            raw_text=raw,
            placeholders_remaining=placeholder_count,
            candidate_facts_present=_detect_candidate_facts(raw),
            extraction_warnings=["cv_extraction_failed"],
        )

    if not isinstance(payload, dict) or not payload:
        return CVSchema(
            raw_text=raw,
            placeholders_remaining=placeholder_count,
            candidate_facts_present=_detect_candidate_facts(raw),
            extraction_warnings=["cv_extraction_failed"],
        )

    skills = normalize_skill_tokens(_coerce_string_list(payload.get("skills")))
    tools = normalize_skill_tokens(_coerce_string_list(payload.get("tools")))
    experience = _coerce_experience(payload.get("experience"))
    education = _coerce_string_list(payload.get("education"))
    summary = str(payload.get("summary") or "").strip()

    candidate_facts_present = _detect_candidate_facts(raw) or bool(
        skills or experience or summary
    )

    warnings: list[str] = []
    if placeholder_count > _PLACEHOLDER_REJECT_THRESHOLD:
        warnings.append("many_placeholders")
    if not candidate_facts_present:
        warnings.append("no_candidate_facts")

    schema = CVSchema(
        raw_text=raw,
        placeholders_remaining=placeholder_count,
        candidate_facts_present=candidate_facts_present,
        summary=summary,
        skills=skills,
        tools=tools,
        experience=experience,
        education=education,
        extraction_warnings=warnings,
    )
    logger.info(
        "extract_cv: skills=%d tools=%d experience=%d placeholders=%d facts=%s",
        len(schema.skills),
        len(schema.tools),
        len(schema.experience),
        schema.placeholders_remaining,
        schema.candidate_facts_present,
    )
    return schema


__all__ = ["extract_cv"]
