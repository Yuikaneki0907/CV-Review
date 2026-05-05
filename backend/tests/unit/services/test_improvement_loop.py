"""Unit tests for :mod:`app.application.services.generation.improvement_loop`.

The loop touches every shared service (jd extractor, cv extractor, scorer,
generator, reviser). The fake AI service below answers each call type
with deterministic data so we can drive stop-condition branches.
"""
from __future__ import annotations

import asyncio
import unittest
from typing import Any, Callable

from app.application.services.generation import run_improvement_loop
from tests.fixtures.fake_ai import FakeIAIService


def _run(coro):
    return asyncio.run(coro)


_REAL_CV_BODY = """# Nguyễn Văn A
candidate@example.com

## Summary
Backend engineer with Python and FastAPI experience.

## Skills
- Python, FastAPI, Docker

## Experience
**Acme Inc** — Senior Engineer | 2022 - now
- Built payments API handling 2 million requests per day using Python
- Reduced p99 latency by 40 percent through query optimisation
- Phát triển hệ thống microservices với Docker

## Education
- B.Sc Computer Science, HUST 2018
"""


def _jd_payload() -> dict:
    return {
        "job_title": "Backend Engineer",
        "seniority": "senior",
        "must_have_keywords": ["python", "fastapi", "docker"],
        "nice_to_have_keywords": [],
        "tools": ["docker"],
        "responsibilities": ["API design"],
        "years_of_experience": 5,
        "domain": None,
    }


def _cv_payload_rich() -> dict:
    """Full CV — hits all must-have keywords + every section. Used for the
    happy-path test where we want the deterministic dimensions to score
    high so the overall lands in PASS."""
    return {
        "summary": "Backend engineer with Python and FastAPI experience.",
        "skills": ["python", "fastapi", "docker"],
        "tools": ["docker"],
        "experience": [
            {
                "role": "Senior Engineer",
                "company": "Acme Inc",
                "period": "2022 - now",
                "bullets": [
                    "Built payments API handling 2 million requests per day using Python",
                    "Reduced p99 latency by 40 percent",
                    "Phát triển hệ thống microservices với Docker",
                ],
            }
        ],
        "education": ["B.Sc Computer Science, HUST 2018"],
    }


def _cv_payload_weak() -> dict:
    """Thin CV — only one keyword present, no education, weak bullets.
    Forces keyword_coverage ≈ 33 and structure < 100 so the overall stays
    below the PASS threshold even when LLM judges return 60."""
    return {
        "summary": "Junior dev.",
        "skills": ["python"],
        "tools": [],
        "experience": [
            {
                "role": "Engineer",
                "company": "Company",
                "period": "2024",
                "bullets": [
                    "Worked on backend tasks",
                ],
            }
        ],
        "education": [],
    }


def _build_structured_factory(
    *, rel: float, summ: float, cv: Callable[[], dict] = _cv_payload_rich
) -> Callable[[str], Any]:
    """Route every structured call to its canned response by prompt keyword."""

    def factory(prompt: str) -> Any:
        lower = prompt.lower()
        if "job description" in lower and "extract structured" in lower:
            return _jd_payload()
        if "cv parser" in lower:
            return cv()
        if "candidate experience bullets" in lower:
            return {"score": rel, "reason": "stub relevance"}
        if "candidate summary" in lower:
            return {"score": summ, "reason": "stub summary"}
        if "rewrite suggestions" in lower:
            return {"suggestions": []}
        return {}

    return factory


class _LoopFakeAI(FakeIAIService):
    """FakeIAIService + programmable ``generate_cv_template``."""

    def __init__(
        self,
        *,
        gen_response: str,
        gen_factory: Callable[..., str] | None = None,
        revise_responses: list[str] | None = None,
        structured_factory: Callable[[str], Any],
    ) -> None:
        super().__init__(structured_factory=structured_factory)
        self._gen_response = gen_response
        self._gen_factory = gen_factory
        self._revise_responses = revise_responses or []
        self.gen_calls = 0
        self.revise_calls = 0

    async def generate_cv_template(
        self,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
        user_profile: dict | None = None,
    ) -> str:
        self.gen_calls += 1
        if self._gen_factory is not None:
            return self._gen_factory(
                job_title=job_title,
                jd_text=jd_text,
                level=level,
                output_format=output_format,
                user_profile=user_profile,
            )
        return self._gen_response

    async def generate_text(self, prompt: str) -> str:
        self.captured_text_prompts.append(prompt)
        idx = self.revise_calls
        self.revise_calls += 1
        if idx < len(self._revise_responses):
            return self._revise_responses[idx]
        # Fall back to the most recent response if the test under-supplied
        # responses; this lets us cap iterations without padding lists.
        return self._revise_responses[-1] if self._revise_responses else _REAL_CV_BODY


class TestLoopPassedThreshold(unittest.TestCase):
    def test_passes_threshold_on_first_iteration(self) -> None:
        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            structured_factory=_build_structured_factory(rel=90, summ=85),
        )
        outcome = _run(
            run_improvement_loop(
                job_title="Backend Engineer",
                jd_text="We need a senior backend engineer with Python, FastAPI, Docker. "
                "Responsibilities include API design and database optimisation.",
                level="Senior",
                ai_service=ai,
                max_iterations=3,
            )
        )
        self.assertEqual(outcome.stopped_reason, "passed_threshold")
        self.assertEqual(len(outcome.iterations), 1)
        self.assertEqual(ai.revise_calls, 0)
        self.assertEqual(outcome.best_index, 0)
        self.assertIsNotNone(outcome.best_analysis)
        self.assertGreaterEqual(outcome.best_analysis.overall_score, 70.0)


class TestLoopMaxIterations(unittest.TestCase):
    def test_caps_at_max_iterations(self) -> None:
        # Weak CV → deterministic dims stay low. LLM judges scale up each
        # iteration (rel=50, 55, 60) so no_improvement does not trigger,
        # but overall never reaches PASS.
        rel_per_iter = [50.0, 55.0, 60.0]
        call_count = {"i": 0}

        base_factory = _build_structured_factory(
            rel=0, summ=0, cv=_cv_payload_weak,
        )

        def factory(prompt: str) -> Any:
            lower = prompt.lower()
            if "candidate experience bullets" in lower:
                idx = min(call_count["i"], len(rel_per_iter) - 1)
                call_count["i"] += 1
                return {"score": rel_per_iter[idx], "reason": "stub rel"}
            if "candidate summary" in lower:
                # mirror the relevance score for simplicity
                idx = min(max(call_count["i"] - 1, 0), len(rel_per_iter) - 1)
                return {"score": rel_per_iter[idx], "reason": "stub sum"}
            return base_factory(prompt)

        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            revise_responses=[_REAL_CV_BODY, _REAL_CV_BODY],
            structured_factory=factory,
        )
        outcome = _run(
            run_improvement_loop(
                job_title="Backend Engineer",
                jd_text="We need a senior backend engineer with Python, FastAPI, Docker. "
                "Responsibilities include API design and database optimisation.",
                level="Senior",
                ai_service=ai,
                max_iterations=3,
            )
        )
        self.assertEqual(outcome.stopped_reason, "max_iterations")
        self.assertEqual(len(outcome.iterations), 3)
        self.assertEqual(ai.revise_calls, 2)
        # Best score should be the last (highest) iteration's score.
        self.assertEqual(outcome.best_index, 2)


class TestLoopNoImprovement(unittest.TestCase):
    def test_stops_when_score_plateaus(self) -> None:
        # Weak CV + LLM judges return identical scores both iterations
        # → overall plateaus, ``no_improvement`` triggers after iter 1.
        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            revise_responses=[_REAL_CV_BODY],
            structured_factory=_build_structured_factory(
                rel=55, summ=55, cv=_cv_payload_weak,
            ),
        )
        outcome = _run(
            run_improvement_loop(
                job_title="Backend Engineer",
                jd_text="We need a senior backend engineer with Python, FastAPI, Docker. "
                "Responsibilities include API design and database optimisation.",
                level="Senior",
                ai_service=ai,
                max_iterations=4,
            )
        )
        self.assertEqual(outcome.stopped_reason, "no_improvement")
        self.assertEqual(len(outcome.iterations), 2)
        self.assertEqual(ai.revise_calls, 1)


class TestLoopInsufficientJD(unittest.TestCase):
    def test_jd_extraction_failure_short_circuits(self) -> None:
        def factory(prompt: str) -> Any:
            return {}  # JD parse failure → JDSchema.empty()

        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            structured_factory=factory,
        )
        outcome = _run(
            run_improvement_loop(
                job_title="Backend Engineer",
                jd_text="We need a senior backend engineer with Python.",
                level="Senior",
                ai_service=ai,
                max_iterations=3,
            )
        )
        self.assertEqual(outcome.stopped_reason, "insufficient_jd")
        self.assertEqual(outcome.iterations, [])
        self.assertEqual(ai.gen_calls, 0)


class TestLoopExtractorFailed(unittest.TestCase):
    def test_empty_generation_marks_extractor_failed(self) -> None:
        ai = _LoopFakeAI(
            gen_response="",  # generator returns nothing
            structured_factory=_build_structured_factory(rel=90, summ=85),
        )
        outcome = _run(
            run_improvement_loop(
                job_title="Backend Engineer",
                jd_text="We need a senior backend engineer with Python, FastAPI, Docker. "
                "Responsibilities include API design and database optimisation.",
                level="Senior",
                ai_service=ai,
                max_iterations=3,
            )
        )
        self.assertEqual(outcome.stopped_reason, "extractor_failed")
        self.assertEqual(len(outcome.iterations), 1)
        self.assertEqual(outcome.best_index, -1)


if __name__ == "__main__":
    unittest.main()
