"""Phase 1 — keyword coverage dimension."""
from __future__ import annotations

from app.application.services.scoring import keyword_coverage
from app.domain.schemas import CVBullet, CVExperienceEntry, CVSchema, JDSchema


def _cv(skills=(), tools=(), bullet_texts=()) -> CVSchema:
    bullets = [CVBullet(text=t) for t in bullet_texts]
    return CVSchema(
        raw_text="...",
        candidate_facts_present=True,
        summary="...",
        skills=list(skills),
        tools=list(tools),
        experience=[CVExperienceEntry(role="r", company="c", period="p", bullets=bullets)]
        if bullets
        else [],
    )


class TestKeywordCoverageHappyPath:
    def test_full_must_have_match_scores_100_when_no_nice_to_haves(self) -> None:
        cv = _cv(skills=["python", "fastapi", "postgresql"])
        jd = JDSchema(raw_text="...", must_have_keywords=["python", "fastapi", "postgresql"])
        dim, report = keyword_coverage.evaluate(cv, jd)
        assert dim.score == 100.0
        assert report.found == ["python", "fastapi", "postgresql"]
        assert report.missing == []
        assert report.density_ok is True

    def test_no_match_scores_zero(self) -> None:
        cv = _cv(skills=["ruby", "rails"])
        jd = JDSchema(raw_text="...", must_have_keywords=["python", "fastapi"])
        dim, report = keyword_coverage.evaluate(cv, jd)
        assert dim.score == 0.0
        assert set(report.missing) == {"python", "fastapi"}
        assert report.density_ok is False

    def test_partial_match_scores_proportionally(self) -> None:
        cv = _cv(skills=["python", "react"])
        # 1 must-have hit, 1 missing → must_score=50; no nice-to-haves
        # 0.7*50 + 0.3*50 = 50
        jd = JDSchema(raw_text="...", must_have_keywords=["python", "fastapi"])
        dim, _ = keyword_coverage.evaluate(cv, jd)
        assert dim.score == 50.0


class TestKeywordCoverageWithNiceToHaves:
    def test_70_30_weighting(self) -> None:
        # All must hit (must=100), zero nice hit (nice=0) → 0.7*100 + 0.3*0 = 70
        cv = _cv(skills=["python"])
        jd = JDSchema(
            raw_text="...",
            must_have_keywords=["python"],
            nice_to_have_keywords=["kafka", "redis"],
        )
        dim, _ = keyword_coverage.evaluate(cv, jd)
        assert dim.score == 70.0

    def test_all_nice_hit_no_must_scores_30(self) -> None:
        cv = _cv(skills=["kafka", "redis"])
        jd = JDSchema(
            raw_text="...",
            must_have_keywords=["python"],
            nice_to_have_keywords=["kafka", "redis"],
        )
        dim, _ = keyword_coverage.evaluate(cv, jd)
        # 0.7*0 + 0.3*100 = 30
        assert dim.score == 30.0


class TestKeywordCoverageBulletScan:
    def test_keyword_in_bullet_prose_counts(self) -> None:
        # CV doesn't list "fastapi" in skills but mentions it in a bullet.
        cv = _cv(
            skills=["python"],
            bullet_texts=["Built a FastAPI service serving 1M req/day"],
        )
        jd = JDSchema(raw_text="...", must_have_keywords=["python", "fastapi"])
        dim, report = keyword_coverage.evaluate(cv, jd)
        assert "fastapi" in report.found
        assert dim.score == 100.0


class TestKeywordCoverageDensity:
    def test_density_below_half_is_not_ok(self) -> None:
        cv = _cv(skills=["python"])
        jd = JDSchema(
            raw_text="...",
            must_have_keywords=["python", "fastapi", "postgresql", "docker"],
        )
        _, report = keyword_coverage.evaluate(cv, jd)
        # 1/4 must-haves found → density 0.25 < 0.5
        assert report.density_ok is False

    def test_density_at_half_is_ok(self) -> None:
        cv = _cv(skills=["python", "fastapi"])
        jd = JDSchema(
            raw_text="...",
            must_have_keywords=["python", "fastapi", "postgresql", "docker"],
        )
        _, report = keyword_coverage.evaluate(cv, jd)
        assert report.density_ok is True


class TestKeywordCoverageEmptyJD:
    def test_no_keywords_at_all_returns_zero(self) -> None:
        cv = _cv(skills=["python"])
        jd = JDSchema(raw_text="...")  # no must, no nice
        dim, report = keyword_coverage.evaluate(cv, jd)
        assert dim.score == 0.0
        assert report.density_ok is False
