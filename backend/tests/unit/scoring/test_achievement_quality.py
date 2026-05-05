"""Phase 1 — achievement quality dimension."""
from __future__ import annotations

from app.application.services.scoring import achievement_quality
from app.domain.schemas import CVBullet, CVExperienceEntry, CVSchema


def _cv(bullets: list[CVBullet]) -> CVSchema:
    return CVSchema(
        raw_text="...",
        candidate_facts_present=True,
        summary="...",
        skills=[],
        experience=[CVExperienceEntry(role="r", company="c", period="p", bullets=bullets)],
    )


class TestAchievementQualityHappyPath:
    def test_all_perfect_bullets_score_100(self) -> None:
        bullets = [
            CVBullet(
                text="Built a payments API serving 2 million requests per day across three regions",
                has_action_verb=True,
                has_metric=True,
            ),
            CVBullet(
                text="Reduced p99 latency by 40 percent through query optimisation on Postgres",
                has_action_verb=True,
                has_metric=True,
            ),
        ]
        dim = achievement_quality.evaluate(_cv(bullets))
        assert dim.score == 100.0

    def test_no_action_verbs_caps_at_60(self) -> None:
        # No action verbs (action 0%), all have metric (metric 100%),
        # all within length range (length 100%)
        # → 0.4*0 + 0.4*100 + 0.2*100 = 60
        bullets = [
            CVBullet(
                text="Worked on a payment system handling 2 million daily requests across three regions",
                has_action_verb=False,
                has_metric=True,
            ),
        ]
        dim = achievement_quality.evaluate(_cv(bullets))
        assert dim.score == 60.0


class TestAchievementQualityEdgeCases:
    def test_zero_bullets_returns_zero(self) -> None:
        cv = CVSchema(raw_text="...", candidate_facts_present=True, experience=[])
        dim = achievement_quality.evaluate(cv)
        assert dim.score == 0.0
        assert "no experience bullets" in dim.reason

    def test_no_metrics_no_action_verbs_no_length_zero(self) -> None:
        bullets = [
            CVBullet(text="Stuff", has_action_verb=False, has_metric=False),
            CVBullet(text="Things", has_action_verb=False, has_metric=False),
        ]
        dim = achievement_quality.evaluate(_cv(bullets))
        assert dim.score == 0.0

    def test_reason_includes_counts(self) -> None:
        bullets = [
            CVBullet(text="Built thing", has_action_verb=True, has_metric=False),
            CVBullet(text="Made stuff", has_action_verb=False, has_metric=False),
        ]
        dim = achievement_quality.evaluate(_cv(bullets))
        assert "1/2" in dim.reason  # one action verb out of two
