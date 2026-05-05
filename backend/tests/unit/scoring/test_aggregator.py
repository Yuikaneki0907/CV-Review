"""Phase 1 — aggregator: overall score, verdict, gap derivation, short-circuits."""
from __future__ import annotations

import asyncio

import pytest

from app.application.services.scoring import aggregator
from app.application.services.scoring.aggregator import (
    compute_overall,
    derive_verdict,
    score_cv,
)
from app.domain.schemas import (
    CVBullet,
    CVExperienceEntry,
    CVSchema,
    DimensionScore,
    DimensionScores,
    JDSchema,
)
from tests.fixtures.fake_ai import FakeIAIService


def _run(coro):
    return asyncio.run(coro)


# ─── verdict thresholds ─────────────────────────────────────────
class TestDeriveVerdict:
    def test_pass_at_70(self) -> None:
        assert derive_verdict(70.0) == "PASS"
        assert derive_verdict(85.5) == "PASS"

    def test_borderline_50_to_69(self) -> None:
        assert derive_verdict(50.0) == "BORDERLINE"
        assert derive_verdict(69.9) == "BORDERLINE"

    def test_fail_below_50(self) -> None:
        assert derive_verdict(49.9) == "FAIL"
        assert derive_verdict(0.0) == "FAIL"


# ─── overall score arithmetic ───────────────────────────────────
def _build_dim_scores(values: tuple[float, float, float, float, float]) -> DimensionScores:
    rel, kw, ach, struc, summ = values
    return DimensionScores(
        relevance=DimensionScore(score=rel),
        keyword_coverage=DimensionScore(score=kw),
        achievement_quality=DimensionScore(score=ach),
        structure=DimensionScore(score=struc),
        summary_alignment=DimensionScore(score=summ),
    )


class TestComputeOverall:
    def test_all_100_yields_100(self) -> None:
        assert compute_overall(_build_dim_scores((100, 100, 100, 100, 100))) == 100.0

    def test_all_zero_yields_zero(self) -> None:
        assert compute_overall(_build_dim_scores((0, 0, 0, 0, 0))) == 0.0

    def test_weighted_sum(self) -> None:
        # relevance=80, keyword=60, achievement=40, structure=20, summary=10
        # 80*0.30 + 60*0.25 + 40*0.20 + 20*0.15 + 10*0.10
        # = 24 + 15 + 8 + 3 + 1 = 51
        assert compute_overall(_build_dim_scores((80, 60, 40, 20, 10))) == 51.0


# ─── score_cv full path with FakeIAIService ─────────────────────
def _real_cv() -> CVSchema:
    return CVSchema(
        raw_text="real cv body",
        candidate_facts_present=True,
        placeholders_remaining=0,
        summary="Senior backend engineer with 5 years building Python services.",
        skills=["python", "fastapi", "postgresql"],
        tools=["docker"],
        experience=[
            CVExperienceEntry(
                role="Senior Engineer",
                company="Acme",
                period="2022-now",
                bullets=[
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
                ],
            )
        ],
        education=["BS CS"],
    )


def _real_jd() -> JDSchema:
    return JDSchema(
        raw_text="...",
        job_title="Senior Backend Engineer",
        seniority="senior",
        must_have_keywords=["python", "fastapi", "postgresql"],
        nice_to_have_keywords=["redis"],
        tools=["docker"],
        responsibilities=["Design APIs", "Optimise databases"],
    )


def _judge_factory(rel_score: float, summary_score: float):
    """LLM that returns different scores depending on which prompt it sees."""
    def factory(prompt: str):
        if "professional summary" in prompt.lower() or "candidate summary" in prompt.lower():
            return {"score": summary_score, "reason": "stub summary judge"}
        if "candidate experience bullets" in prompt.lower():
            return {"score": rel_score, "reason": "stub relevance judge"}
        # suggestions prompt
        if "rewrite suggestions" in prompt.lower() or "suggestions" in prompt.lower():
            return {
                "suggestions": [
                    {
                        "section": "Summary",
                        "issue": "missing keyword",
                        "current": "...",
                        "suggested": "Senior Python engineer with FastAPI experience",
                    }
                ]
            }
        return {"score": 0, "reason": "unknown prompt"}
    return factory


class TestScoreCVHappyPath:
    def test_real_cv_real_jd_scores_pass(self) -> None:
        fake = FakeIAIService(structured_factory=_judge_factory(rel_score=90, summary_score=85))
        result = _run(score_cv(_real_cv(), _real_jd(), fake))
        assert result.verdict == "PASS"
        assert result.overall_score >= 70
        # Suggestions only generated when verdict != PASS — skip on PASS.
        assert result.suggestions == []


class TestScoreCVShortCircuits:
    def test_unusable_jd_short_circuits_fail(self) -> None:
        fake = FakeIAIService(structured_response={"score": 100})
        result = _run(score_cv(_real_cv(), JDSchema.empty("jd_too_short"), fake))
        assert result.verdict == "FAIL"
        assert result.overall_score == 0.0
        assert result.analysis_meta.get("short_circuit") == "insufficient_jd"
        # LLM judges must NOT be called on insufficient_jd.
        assert fake.captured_prompts == []

    def test_template_only_cv_short_circuits_fail(self) -> None:
        template_cv = CVSchema(
            raw_text="...",
            candidate_facts_present=False,
            placeholders_remaining=10,
            summary="",
            skills=[],
            experience=[],
        )
        fake = FakeIAIService(structured_response={"score": 100})
        result = _run(score_cv(template_cv, _real_jd(), fake))
        assert result.verdict == "FAIL"
        assert result.analysis_meta.get("short_circuit") == "template_only_cv"
        # Keyword report is still populated so the generator can see what
        # it should inject in Phase 2.
        assert "missing" in result.keyword_report.model_dump()
        # LLM judges must NOT be called on template-only short-circuit.
        assert fake.captured_prompts == []


class TestScoreCVGapAnalysis:
    def test_missing_keywords_become_critical(self) -> None:
        cv = _real_cv().model_copy(update={"skills": ["python"]})  # drop fastapi + postgresql
        fake = FakeIAIService(structured_factory=_judge_factory(rel_score=60, summary_score=50))
        result = _run(score_cv(cv, _real_jd(), fake))
        joined = " ".join(result.gap_analysis.critical_missing)
        assert "fastapi" in joined
        assert "postgresql" in joined

    def test_borderline_triggers_suggestions(self) -> None:
        cv = _real_cv().model_copy(update={"skills": ["python"]})
        fake = FakeIAIService(structured_factory=_judge_factory(rel_score=60, summary_score=60))
        result = _run(score_cv(cv, _real_jd(), fake))
        assert result.verdict in {"BORDERLINE", "FAIL"}
        # Suggestions LLM call should fire.
        assert len(result.suggestions) >= 1
        assert result.suggestions[0].section


class TestScoreCVJudgeFailure:
    def test_relevance_judge_exception_does_not_crash(self) -> None:
        # Factory raises on relevance prompt only.
        def factory(prompt: str):
            if "candidate experience bullets" in prompt.lower():
                raise RuntimeError("LLM down")
            if "summary" in prompt.lower():
                return {"score": 80, "reason": "stub"}
            return {"suggestions": []}
        fake = FakeIAIService(structured_factory=factory)
        result = _run(score_cv(_real_cv(), _real_jd(), fake))
        # Relevance dimension clamps to 0 with judge_failed reason.
        assert result.dimension_scores.relevance.score == 0.0
        assert "judge_failed" in result.dimension_scores.relevance.reason
        # Pipeline still produces a verdict — must not raise.
        assert result.verdict in {"PASS", "BORDERLINE", "FAIL"}
