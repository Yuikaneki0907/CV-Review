"""Structure dimension (15% weight).

Pure-Python deterministic. Checks:
- presence of the four core sections (Summary, Skills, Experience, Education)
- placeholder pollution (each remaining ``[...]`` / ``<...>`` deducts)
- candidate facts present (real evidence of a real candidate)

Scoring::

    section_score = sections_present / 4 * 100
    placeholder_penalty = min(30, placeholders_remaining * 5)
    facts_penalty = 25 if not candidate_facts_present else 0
    score = max(0, section_score - placeholder_penalty - facts_penalty)
"""
from __future__ import annotations

from app.domain.schemas import CVSchema, DimensionScore

_PLACEHOLDER_PENALTY_PER_OCCURRENCE = 5.0
_PLACEHOLDER_PENALTY_CAP = 30.0
_NO_CANDIDATE_FACTS_PENALTY = 25.0


def _present_sections(cv: CVSchema) -> list[str]:
    present: list[str] = []
    if cv.summary.strip():
        present.append("summary")
    if cv.skills:
        present.append("skills")
    if cv.experience and any(e.bullets for e in cv.experience):
        present.append("experience")
    if cv.education:
        present.append("education")
    return present


def evaluate(cv: CVSchema) -> DimensionScore:
    """Score the structural soundness of the CV.

    Args:
        cv: The candidate's structured CV.

    Returns:
        :class:`DimensionScore` 0..100. A CV with all four sections
        present, zero placeholders, and real candidate facts scores 100.
    """
    present = _present_sections(cv)
    section_score = (len(present) / 4.0) * 100.0

    placeholder_penalty = min(
        _PLACEHOLDER_PENALTY_CAP,
        cv.placeholders_remaining * _PLACEHOLDER_PENALTY_PER_OCCURRENCE,
    )
    facts_penalty = 0.0 if cv.candidate_facts_present else _NO_CANDIDATE_FACTS_PENALTY

    score = section_score - placeholder_penalty - facts_penalty
    score = max(0.0, min(100.0, score))

    missing = [s for s in ("summary", "skills", "experience", "education") if s not in present]
    reason_parts = [f"{len(present)}/4 core sections present"]
    if missing:
        reason_parts.append(f"missing: {', '.join(missing)}")
    if cv.placeholders_remaining:
        reason_parts.append(f"{cv.placeholders_remaining} placeholders remain")
    if not cv.candidate_facts_present:
        reason_parts.append("no concrete candidate facts detected")
    reason = "; ".join(reason_parts)

    return DimensionScore(score=round(score, 1), reason=reason)
