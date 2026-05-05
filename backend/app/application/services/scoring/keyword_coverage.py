"""Keyword Coverage dimension (25% weight).

Pure-Python deterministic. Compares the normalised JD keyword universe
against the normalised CV token universe. No LLM call.

Score formula::

    must_score = matched_must / total_must * 100        # 0..100
    nice_score = matched_nice / max(total_nice, 1) * 100
    score      = 0.7 * must_score + 0.3 * nice_score

If the JD has zero must-have keywords (``jd.is_usable is False``), this
dimension cannot evaluate and returns ``(0.0, reason)``; the aggregator
flags the analysis as ``insufficient_jd``.
"""
from __future__ import annotations

from app.application.services.shared.skill_normalisation import normalize_skill_token
from app.domain.schemas import CVSchema, DimensionScore, JDSchema, KeywordReport


_DENSITY_OK_THRESHOLD = 0.5  # at least half of must-haves must appear


def _cv_token_universe(cv: CVSchema) -> set[str]:
    """All normalised tokens the CV exposes for keyword matching."""
    tokens: set[str] = set()
    tokens.update(cv.skills)
    tokens.update(cv.tools)
    # Pull additional tokens from bullets (already normalised when
    # they came out of extract_cv, but bullet text is free-form prose so
    # we also do a substring scan in the aggregator below).
    return tokens


def _bullet_text(cv: CVSchema) -> str:
    """All experience bullets joined for substring matching.

    The CV extractor stores bullets verbatim — keywords inside prose
    (e.g. "Built a FastAPI service") should count even if the candidate
    didn't list them in a Skills section. The cost of a substring scan
    is trivial.
    """
    parts: list[str] = []
    for entry in cv.experience:
        for bullet in entry.bullets:
            parts.append(bullet.text)
    return "\n".join(parts).lower()


def _is_present(token: str, token_universe: set[str], bullet_blob: str) -> bool:
    """True if a normalised JD keyword is present in the CV.

    Matches against:
    - the set of normalised CV skill/tool tokens, OR
    - a substring of the bullet prose blob (lower-cased).
    """
    if token in token_universe:
        return True
    # Substring match — guard against single-character tokens that would
    # produce too many false positives.
    if len(token) >= 2 and token in bullet_blob:
        return True
    return False


def evaluate(cv: CVSchema, jd: JDSchema) -> tuple[DimensionScore, KeywordReport]:
    """Score keyword coverage and produce the keyword report.

    Args:
        cv: The candidate's structured CV.
        jd: The structured JD; must have ``is_usable`` to score.

    Returns:
        ``(DimensionScore, KeywordReport)`` — the dimension score (0..100)
        and the detailed found/missing breakdown used by Phase 3 to
        target revisions.
    """
    must_have = [normalize_skill_token(k) for k in jd.must_have_keywords if k]
    must_have = [k for k in must_have if k]
    nice = [normalize_skill_token(k) for k in jd.nice_to_have_keywords if k]
    nice = [k for k in nice if k]

    if not must_have and not nice:
        return (
            DimensionScore(score=0.0, reason="JD has no keywords to score against"),
            KeywordReport(found=[], missing=[], density_ok=False),
        )

    token_universe = _cv_token_universe(cv)
    bullet_blob = _bullet_text(cv)

    matched_must = [k for k in must_have if _is_present(k, token_universe, bullet_blob)]
    missing_must = [k for k in must_have if k not in matched_must]
    matched_nice = [k for k in nice if _is_present(k, token_universe, bullet_blob)]
    missing_nice = [k for k in nice if k not in matched_nice]

    must_score = (
        (len(matched_must) / len(must_have)) * 100.0
        if must_have
        else 0.0
    )
    nice_score = (
        (len(matched_nice) / len(nice)) * 100.0
        if nice
        else must_score  # if there are no nice-to-haves, weight goes entirely to must
    )
    score = 0.7 * must_score + 0.3 * nice_score
    score = max(0.0, min(100.0, score))

    density_ok = bool(must_have) and (len(matched_must) / len(must_have)) >= _DENSITY_OK_THRESHOLD

    reason_parts = [
        f"{len(matched_must)}/{len(must_have)} must-have keywords found",
    ]
    if nice:
        reason_parts.append(f"{len(matched_nice)}/{len(nice)} nice-to-have found")
    if not density_ok and must_have:
        reason_parts.append("keyword density below ATS threshold")
    reason = "; ".join(reason_parts)

    report = KeywordReport(
        found=matched_must + matched_nice,
        missing=missing_must + missing_nice,
        density_ok=density_ok,
    )
    return DimensionScore(score=round(score, 1), reason=reason), report
