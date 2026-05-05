"""Achievement Quality dimension (20% weight).

Pure-Python deterministic. Operates over the ``has_action_verb`` /
``has_metric`` tags that ``shared.cv_extractor`` set on each bullet, so
this module never calls an LLM.

Score components::

    action_pct  = bullets with action verb / total bullets
    metric_pct  = bullets with metric      / total bullets
    length_pct  = bullets within 8-40 words / total bullets
    score       = 0.4*action + 0.4*metric + 0.2*length      (×100)

A CV with zero bullets returns score 0 with the reason
"no experience bullets".
"""
from __future__ import annotations

from app.domain.schemas import CVSchema, DimensionScore

_MIN_WORDS = 8
_MAX_WORDS = 40


def _all_bullets(cv: CVSchema) -> list:
    bullets = []
    for entry in cv.experience:
        bullets.extend(entry.bullets)
    return bullets


def _word_count_ok(text: str) -> bool:
    n = len(text.split())
    return _MIN_WORDS <= n <= _MAX_WORDS


def evaluate(cv: CVSchema) -> DimensionScore:
    """Score the achievement quality of the candidate's experience bullets.

    Args:
        cv: The candidate's structured CV.

    Returns:
        :class:`DimensionScore` 0..100 with a human-readable reason.
    """
    bullets = _all_bullets(cv)
    total = len(bullets)
    if total == 0:
        return DimensionScore(score=0.0, reason="no experience bullets to score")

    action_count = sum(1 for b in bullets if b.has_action_verb)
    metric_count = sum(1 for b in bullets if b.has_metric)
    length_count = sum(1 for b in bullets if _word_count_ok(b.text))

    action_pct = action_count / total
    metric_pct = metric_count / total
    length_pct = length_count / total

    score = (0.4 * action_pct + 0.4 * metric_pct + 0.2 * length_pct) * 100.0
    score = max(0.0, min(100.0, score))

    reason = (
        f"{action_count}/{total} bullets start with an action verb; "
        f"{metric_count}/{total} include a quantifiable metric; "
        f"{length_count}/{total} are within the recommended length"
    )
    return DimensionScore(score=round(score, 1), reason=reason)
