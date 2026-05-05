"""Phase 1 — AnalyzeCVUseCase end-to-end (LLM mocked).

Exercises the full pipeline through a fake repo + fake AI service:
- jd extraction
- cv extraction
- 5-dim scoring
- short-circuit paths
- SSE streaming variant
"""
from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from app.application.use_cases.analyze_cv import AnalyzeCVUseCase
from app.domain.entities.analysis_result import AnalysisResult
from tests.fixtures.fake_ai import FakeIAIService


def _run(coro):
    return asyncio.run(coro)


class FakeAnalysisRepo:
    """Minimal in-memory repo for the analyzer pipeline."""

    def __init__(self) -> None:
        self._rows: dict[UUID, AnalysisResult] = {}

    async def create(self, analysis: AnalysisResult) -> AnalysisResult:
        self._rows[analysis.id] = analysis
        return analysis

    async def get_by_id(self, analysis_id: UUID) -> AnalysisResult | None:
        return self._rows.get(analysis_id)

    async def update(self, analysis: AnalysisResult) -> AnalysisResult:
        self._rows[analysis.id] = analysis
        return analysis


_REAL_CV_TEXT = """# Nguyen A
candidate@example.com | github.com/nguyena

## Summary
Senior backend engineer with 5 years building distributed Python services.

## Skills
Python, FastAPI, PostgreSQL, Docker

## Experience
**Acme Inc** - Senior Engineer | 2022 - now
- Built a payments API handling 2 million requests per day
- Reduced p99 latency by 40 percent through query optimisation
- Led migration from MongoDB to PostgreSQL

## Education
B.Sc. Computer Science, HUST 2018
"""

_REAL_JD_TEXT = (
    "We are hiring a Senior Backend Engineer. "
    "Requirements: 5+ years experience with Python and FastAPI. "
    "Must have PostgreSQL and Docker experience. "
    "Responsibilities include API design and database optimisation."
)


def _make_factory(*, rel: float = 90, summ: float = 85) -> Any:
    """Build a structured-response factory that responds to each prompt by content."""
    def factory(prompt: str):
        lower = prompt.lower()
        if "job description" in lower and "extract structured fields" in lower:
            return {
                "job_title": "Senior Backend Engineer",
                "seniority": "senior",
                "must_have_keywords": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "nice_to_have_keywords": [],
                "tools": ["Docker"],
                "responsibilities": ["API design", "Database optimisation"],
                "years_of_experience": "5+",
                "domain": None,
            }
        if "cv parser" in lower:
            return {
                "summary": "Senior backend engineer with 5 years building distributed Python services.",
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "tools": ["Docker"],
                "experience": [
                    {
                        "role": "Senior Engineer",
                        "company": "Acme Inc",
                        "period": "2022 - now",
                        "bullets": [
                            "Built a payments API handling 2 million requests per day",
                            "Reduced p99 latency by 40 percent through query optimisation",
                            "Led migration from MongoDB to PostgreSQL",
                        ],
                    }
                ],
                "education": ["B.Sc. Computer Science, HUST 2018"],
            }
        if "candidate experience bullets" in lower:
            return {"score": rel, "reason": "stub relevance"}
        if "candidate summary" in lower:
            return {"score": summ, "reason": "stub summary"}
        if "rewrite suggestions" in lower:
            return {
                "suggestions": [
                    {
                        "section": "Summary",
                        "issue": "missing keyword",
                        "current": "...",
                        "suggested": "...",
                    }
                ]
            }
        return {}
    return factory


class TestAnalyzeCVUseCaseHappyPath:
    def test_real_cv_and_jd_produces_pass(self) -> None:
        repo = FakeAnalysisRepo()
        analysis = AnalysisResult(
            user_id=uuid4(),
            cv_filename="cv.md",
            cv_text=_REAL_CV_TEXT,
            jd_text=_REAL_JD_TEXT,
        )
        _run(repo.create(analysis))

        ai = FakeIAIService(structured_factory=_make_factory(rel=90, summ=85))
        use_case = AnalyzeCVUseCase(repo, ai)
        _run(use_case.execute(analysis.id))

        persisted = _run(repo.get_by_id(analysis.id))
        assert persisted is not None
        assert persisted.status.value == "completed"
        # New schema available via analysis_meta["result"].
        meta = persisted.analysis_meta or {}
        assert "result" in meta
        result = meta["result"]
        assert result["verdict"] == "PASS"
        assert result["overall_score"] >= 70
        # Legacy back-compat fields populated.
        assert persisted.score is not None
        assert persisted.score.overall == result["overall_score"]


class TestAnalyzeCVUseCaseTemplateShortCircuit:
    def test_template_only_cv_returns_fail_without_llm_judges(self) -> None:
        template_cv = """# [Họ và tên]
[Email] | [Số điện thoại]

## Mục tiêu
[Mục tiêu nghề nghiệp]

## Kỹ năng
- [Kỹ năng 1]
- [Kỹ năng 2]
- [Kỹ năng 3]

## Kinh nghiệm
- Làm việc tại [Tên công ty] [Năm bắt đầu] - [Năm kết thúc]
- [Mô tả công việc]
"""
        repo = FakeAnalysisRepo()
        analysis = AnalysisResult(
            user_id=uuid4(),
            cv_filename="template.md",
            cv_text=template_cv,
            jd_text=_REAL_JD_TEXT,
        )
        _run(repo.create(analysis))

        # CV extractor will be called once; but downstream LLM judges (relevance,
        # summary alignment, suggestions) must NOT fire on template short-circuit.
        prompt_count_when_done: list[int] = []

        def factory(prompt: str):
            lower = prompt.lower()
            if "job description" in lower and "extract structured fields" in lower:
                return {
                    "must_have_keywords": ["python", "fastapi"],
                    "responsibilities": ["API design"],
                }
            if "cv parser" in lower:
                # The extractor returns nothing useful — placeholders dominate.
                return {"summary": "", "skills": [], "tools": [], "experience": [], "education": []}
            # Any further prompt would indicate a leak past the short-circuit.
            prompt_count_when_done.append(1)
            return {}

        ai = FakeIAIService(structured_factory=factory)
        use_case = AnalyzeCVUseCase(repo, ai)
        _run(use_case.execute(analysis.id))

        persisted = _run(repo.get_by_id(analysis.id))
        assert persisted is not None
        meta = persisted.analysis_meta or {}
        assert meta["result"]["verdict"] == "FAIL"
        assert meta["result"]["analysis_meta"]["short_circuit"] == "template_only_cv"
        assert prompt_count_when_done == [], (
            "LLM judges should not run on template short-circuit"
        )


class TestAnalyzeCVUseCaseStream:
    def test_stream_yields_expected_events_in_order(self) -> None:
        repo = FakeAnalysisRepo()
        analysis = AnalysisResult(
            user_id=uuid4(),
            cv_filename="cv.md",
            cv_text=_REAL_CV_TEXT,
            jd_text=_REAL_JD_TEXT,
        )
        _run(repo.create(analysis))

        ai = FakeIAIService(structured_factory=_make_factory(rel=90, summ=85))
        use_case = AnalyzeCVUseCase(repo, ai)

        async def collect():
            chunks = []
            async for chunk in use_case.execute_stream(analysis.id):
                chunks.append(chunk)
            return chunks

        chunks = _run(collect())
        joined = "".join(chunks)
        assert "event: analysis_start" in joined
        assert "event: analysis_step" in joined
        assert "event: analysis_result" in joined
        assert "event: analysis_done" in joined
        # Specific result types appear in correct order.
        scores_pos = joined.find('"type": "scores"')
        kw_pos = joined.find('"type": "keyword_report"')
        done_pos = joined.find("analysis_done")
        assert 0 < scores_pos < kw_pos < done_pos


class TestAnalyzeCVUseCaseMissing:
    def test_unknown_analysis_raises_value_error(self) -> None:
        repo = FakeAnalysisRepo()
        ai = FakeIAIService()
        use_case = AnalyzeCVUseCase(repo, ai)
        try:
            _run(use_case.execute(uuid4()))
        except ValueError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("expected ValueError for missing analysis")
