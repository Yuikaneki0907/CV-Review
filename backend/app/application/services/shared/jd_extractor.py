"""Job Description → JDSchema.

The single function every other module imports when it needs a
structured JD. Both Phase 1's scorer and Phase 2's generator bind to
the JDSchema returned here — there is no other JD parser.
"""
from __future__ import annotations

import re
from typing import Any

from app.application.interfaces.ai_service import IAIService
from app.application.prompts import render_prompt
from app.application.services.shared.skill_normalisation import (
    normalize_skill_token,
    normalize_skill_tokens,
)
from app.domain.schemas import JDSchema, Seniority
from app.logger import get_logger

logger = get_logger("app.application.services.shared.jd_extractor")

_MIN_JD_CHARS = 60
_VALID_SENIORITIES: tuple[Seniority, ...] = (
    "intern",
    "fresher",
    "junior",
    "mid",
    "senior",
    "lead",
    "manager",
    "unknown",
)


def _coerce_seniority(value: Any) -> Seniority:
    """Map an LLM-returned seniority value onto our enum."""
    if not isinstance(value, str):
        return "unknown"
    lowered = value.strip().lower()
    # Common synonyms.
    if lowered in {"middle", "intermediate"}:
        return "mid"
    if lowered in {"sr", "senior engineer"}:
        return "senior"
    if lowered in _VALID_SENIORITIES:
        return lowered  # type: ignore[return-value]
    return "unknown"


def _coerce_string_list(value: Any) -> list[str]:
    """Best-effort coercion of an LLM payload to ``list[str]``."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _coerce_int_or_none(value: Any) -> int | None:
    """Pull an integer YOE out of a free-form value, else None."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                return None
    return None


async def extract_jd(jd_text: str, ai_service: IAIService) -> JDSchema:
    """Extract a structured :class:`JDSchema` from raw JD text.

    Args:
        jd_text: Raw JD body as supplied by the user / file parser.
        ai_service: Concrete :class:`IAIService` implementation.

    Returns:
        Fully populated :class:`JDSchema`. On any failure — empty input,
        LLM error, malformed JSON — returns ``JDSchema.empty(reason=...)``
        rather than raising, so callers can branch on
        ``schema.extraction_warnings`` / ``schema.is_usable``.
    """
    raw = (jd_text or "").strip()
    if len(raw) < _MIN_JD_CHARS:
        logger.info("extract_jd: jd_too_short (len=%d)", len(raw))
        return JDSchema.empty("jd_too_short", raw_text=raw)

    prompt = render_prompt("jd_extraction", jd_text=raw)
    try:
        payload = await ai_service.generate_structured(prompt, expect_list=False)
    except Exception as exc:
        logger.warning("extract_jd: ai_service error: %s", exc, exc_info=True)
        return JDSchema.empty("jd_extraction_failed", raw_text=raw)

    if not isinstance(payload, dict) or not payload:
        logger.warning(
            "extract_jd: empty/invalid payload (type=%s)", type(payload).__name__
        )
        return JDSchema.empty("jd_extraction_failed", raw_text=raw)

    must_have = normalize_skill_tokens(_coerce_string_list(payload.get("must_have_keywords")))
    nice = normalize_skill_tokens(_coerce_string_list(payload.get("nice_to_have_keywords")))
    tools = normalize_skill_tokens(_coerce_string_list(payload.get("tools")))
    responsibilities = _coerce_string_list(payload.get("responsibilities"))[:8]

    warnings: list[str] = []
    if not must_have:
        warnings.append("no_required_skills_found")

    job_title = str(payload.get("job_title") or "").strip()
    domain_raw = payload.get("domain")
    domain = str(domain_raw).strip() if isinstance(domain_raw, str) and domain_raw.strip() else None

    schema = JDSchema(
        raw_text=raw,
        job_title=job_title,
        seniority=_coerce_seniority(payload.get("seniority")),
        must_have_keywords=must_have,
        nice_to_have_keywords=nice,
        tools=tools,
        responsibilities=responsibilities,
        years_of_experience=_coerce_int_or_none(payload.get("years_of_experience")),
        domain=domain,
        extraction_warnings=warnings,
    )
    logger.info(
        "extract_jd: title=%r seniority=%s must_have=%d nice=%d tools=%d resp=%d",
        schema.job_title,
        schema.seniority,
        len(schema.must_have_keywords),
        len(schema.nice_to_have_keywords),
        len(schema.tools),
        len(schema.responsibilities),
    )
    return schema


# Re-export for callers that want token-level normalisation without
# importing the skill_normalisation module directly.
__all__ = ["extract_jd", "normalize_skill_token"]
