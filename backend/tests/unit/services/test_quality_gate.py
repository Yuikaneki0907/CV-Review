"""Unit tests for :mod:`app.application.services.generation.quality_gate`."""
from __future__ import annotations

import asyncio
import unittest
from typing import Any

from app.application.services.generation import ensure_quality
from app.application.services.generation.quality_gate import (
    DEFAULT_MAX_REVISIONS,
    DEFAULT_PASS_THRESHOLD,
)
from tests.unit.services.test_improvement_loop import (
    _LoopFakeAI,
    _REAL_CV_BODY,
    _build_structured_factory,
    _cv_payload_weak,
)


def _run(coro):
    return asyncio.run(coro)


class TestQualityGateDefaults(unittest.TestCase):
    def test_default_pass_threshold_is_80(self) -> None:
        self.assertEqual(DEFAULT_PASS_THRESHOLD, 80.0)

    def test_default_max_revisions_is_two(self) -> None:
        # Bumped from 1 → 2 in BE-3 to give the gate a real chance at
        # converging without invoking the dedicated improve-loop.
        self.assertEqual(DEFAULT_MAX_REVISIONS, 2)


_JD_TEXT = (
    "We need a senior backend engineer with Python, FastAPI, Docker. "
    "Responsibilities include API design and database optimisation."
)


class TestQualityGatePassImmediately(unittest.TestCase):
    """Score >= 80 on first analyze — no revision needed."""

    def test_high_score_returns_original_content(self) -> None:
        ai = _LoopFakeAI(
            gen_response="",  # ensure_quality never calls generate_cv_template
            structured_factory=_build_structured_factory(rel=90, summ=90),
        )
        result = _run(
            ensure_quality(
                cv_content=_REAL_CV_BODY,
                jd_text=_JD_TEXT,
                ai_service=ai,
                pass_threshold=80.0,
            )
        )
        self.assertTrue(result.passed_gate)
        self.assertEqual(result.revisions_used, 0)
        self.assertEqual(result.content, _REAL_CV_BODY)
        self.assertGreaterEqual(result.final_score, 80.0)
        # No reviser call was made.
        self.assertEqual(ai.revise_calls, 0)


class TestQualityGateNeedsRevision(unittest.TestCase):
    """First analyze < threshold; one revision pushes the score up.

    To trigger a revision the CV must score below ``pass_threshold`` on
    the first analyze. We force this by:
      * using a weak CV extractor payload (low structure / achievement)
      * making LLM judges (relevance + summary_alignment) return low
        scores on the first analyze and high scores after revision
    The judge call ordering is deterministic: 2 calls per analyze, so
    we flip behaviour at call #3.
    """

    def test_revises_once_when_below_threshold(self) -> None:
        judge_calls = {"n": 0}

        def factory(prompt: str) -> Any:
            lower = prompt.lower()
            if "job description" in lower and "extract structured" in lower:
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
            if "cv parser" in lower:
                # Weak payload: thin sections, no keywords matched → low
                # deterministic dimensions so judge scores actually move
                # the overall.
                return {
                    "summary": "Junior dev.",
                    "skills": ["python"],
                    "tools": [],
                    "experience": [
                        {
                            "role": "Engineer",
                            "company": "X",
                            "period": "2024",
                            "bullets": ["Worked on tasks"],
                        }
                    ],
                    "education": [],
                }
            if "candidate experience bullets" in lower or "candidate summary" in lower:
                judge_calls["n"] += 1
                # First analyze uses calls 1,2; revision analyze uses 3,4.
                if judge_calls["n"] <= 2:
                    return {"score": 30.0, "reason": "stub low"}
                return {"score": 100.0, "reason": "stub high"}
            return {}

        ai = _LoopFakeAI(
            gen_response="",
            revise_responses=["# Revised CV\n## Summary\n" + ("Better content. " * 20)],
            structured_factory=factory,
        )

        result = _run(
            ensure_quality(
                cv_content=_REAL_CV_BODY,
                jd_text=_JD_TEXT,
                ai_service=ai,
                pass_threshold=80.0,
                max_revisions=1,
            )
        )
        # Gate detected sub-threshold initial score and ran exactly 1 revision.
        self.assertEqual(ai.revise_calls, 1)
        self.assertEqual(result.revisions_used, 1)
        # Score improved post-revision (judges returned 100 instead of 30).
        self.assertGreater(result.final_score, result.initial_score)


class TestQualityGateShortCircuits(unittest.TestCase):
    def test_jd_unusable_skips_gate(self) -> None:
        ai = _LoopFakeAI(
            gen_response="",
            structured_factory=lambda prompt: {},  # JD parse fails
        )
        result = _run(
            ensure_quality(
                cv_content=_REAL_CV_BODY,
                jd_text=_JD_TEXT,
                ai_service=ai,
            )
        )
        self.assertFalse(result.passed_gate)
        self.assertEqual(result.revisions_used, 0)
        self.assertIn("jd_unusable", result.warnings)
        self.assertEqual(result.content, _REAL_CV_BODY)
        # CV extractor + scorer should never have been called either.
        self.assertEqual(ai.revise_calls, 0)

    def test_template_cv_skips_gate(self) -> None:
        # CV is recognised but extractor returns is_template_only=True.
        def factory(prompt: str) -> Any:
            lower = prompt.lower()
            if "job description" in lower and "extract structured" in lower:
                return {
                    "job_title": "Backend",
                    "seniority": "senior",
                    "must_have_keywords": ["python"],
                    "nice_to_have_keywords": [],
                    "tools": [],
                    "responsibilities": [],
                    "years_of_experience": None,
                    "domain": None,
                }
            if "cv parser" in lower:
                return {}  # empty extraction → CV becomes template-only
            return {}

        ai = _LoopFakeAI(gen_response="", structured_factory=factory)
        result = _run(
            ensure_quality(
                cv_content="# [Họ và tên]\n## [Section]\n- [Item]",
                jd_text=_JD_TEXT,
                ai_service=ai,
            )
        )
        self.assertFalse(result.passed_gate)
        self.assertEqual(result.revisions_used, 0)
        self.assertIn("cv_template_only", result.warnings)


class TestQualityGateMaxRevisionsCap(unittest.TestCase):
    """Even after max_revisions revisions, if still below threshold we stop."""

    def test_stops_after_max_revisions(self) -> None:
        # Keep scores low forever → max_revisions cap kicks in.
        ai = _LoopFakeAI(
            gen_response="",
            revise_responses=[_REAL_CV_BODY, _REAL_CV_BODY],
            structured_factory=_build_structured_factory(
                rel=40, summ=40, cv=_cv_payload_weak,
            ),
        )
        result = _run(
            ensure_quality(
                cv_content=_REAL_CV_BODY,
                jd_text=_JD_TEXT,
                ai_service=ai,
                pass_threshold=80.0,
                max_revisions=2,
            )
        )
        self.assertFalse(result.passed_gate)
        self.assertEqual(result.revisions_used, 2)
        # Best content might still be the original (if revisions didn't help).
        self.assertGreaterEqual(result.final_score, result.initial_score)


if __name__ == "__main__":
    unittest.main()
