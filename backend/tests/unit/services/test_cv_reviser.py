"""Unit tests for :mod:`app.application.services.generation.cv_reviser`."""
from __future__ import annotations

import asyncio
import unittest

from app.application.services.generation import RevisionOutput, revise_cv
from app.domain.schemas import GapAnalysis, JDSchema
from tests.fixtures.fake_ai import FakeIAIService


def _run(coro):
    return asyncio.run(coro)


def _jd() -> JDSchema:
    return JDSchema(
        raw_text="we need python",
        job_title="Backend Engineer",
        seniority="senior",
        must_have_keywords=["python", "fastapi"],
        nice_to_have_keywords=[],
        tools=["docker"],
        responsibilities=["api design"],
        years_of_experience=5,
        domain=None,
        extraction_warnings=[],
    )


def _gap() -> GapAnalysis:
    return GapAnalysis(
        critical_missing=["missing keyword: docker", "CV is missing a Summary section"],
        improvable=["achievement quality below 70: weak bullets"],
    )


_REVISED_CV = """# Nguyễn Văn A
candidate@example.com

## Summary
Backend engineer with Python and FastAPI experience.

## Skills
- Python, FastAPI, Docker

## Experience
- Built APIs using Python and FastAPI at Acme Inc 2024.
- Triển khai Docker cho microservices.
"""


class TestReviserHappyPath(unittest.TestCase):
    def test_prompt_includes_gap_items_and_keywords(self) -> None:
        ai = FakeIAIService(text_response=_REVISED_CV)
        result = _run(
            revise_cv(
                current_cv="# old cv\n## Skills\n- Python",
                gap=_gap(),
                jd=_jd(),
                ai_service=ai,
                job_title="Backend Engineer",
                level="Senior",
                missing_keywords=["docker"],
            )
        )
        self.assertIsInstance(result, RevisionOutput)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(ai.captured_text_prompts), 1)
        prompt = ai.captured_text_prompts[0]
        self.assertIn("missing keyword: docker", prompt)
        self.assertIn("CV is missing a Summary section", prompt)
        self.assertIn("docker", prompt)  # from missing_must_have
        self.assertIn("Backend Engineer", prompt)
        # current CV body must appear so reviser doesn't start from scratch.
        self.assertIn("# old cv", prompt)

    def test_falls_back_to_jd_must_have_when_missing_keywords_not_given(self) -> None:
        ai = FakeIAIService(text_response=_REVISED_CV)
        _run(
            revise_cv(
                current_cv="# old cv",
                gap=_gap(),
                jd=_jd(),
                ai_service=ai,
            )
        )
        prompt = ai.captured_text_prompts[0]
        # JD must_have includes python + fastapi; both should be present.
        self.assertIn("python", prompt)
        self.assertIn("fastapi", prompt)

    def test_counts_placeholders_in_revised_output(self) -> None:
        body = "# [Họ và tên]\n[Email]\n## Summary\nABC " + ("x" * 80)
        ai = FakeIAIService(text_response=body)
        result = _run(
            revise_cv(
                current_cv="# old",
                gap=_gap(),
                jd=_jd(),
                ai_service=ai,
            )
        )
        # Two placeholders: [Họ và tên], [Email].
        self.assertEqual(result.placeholders_remaining, 2)


class TestReviserFailureModes(unittest.TestCase):
    def test_ai_failure_returns_warnings(self) -> None:
        ai = FakeIAIService(raise_on_text=RuntimeError("provider down"))
        result = _run(
            revise_cv(
                current_cv="# old",
                gap=_gap(),
                jd=_jd(),
                ai_service=ai,
            )
        )
        self.assertEqual(result.content, "")
        self.assertIn("ai_provider_failed", result.warnings)
        self.assertIn("ai_returned_empty", result.warnings)
        self.assertFalse(result.is_valid)

    def test_short_response_flagged(self) -> None:
        ai = FakeIAIService(text_response="# tiny")
        result = _run(
            revise_cv(
                current_cv="# old",
                gap=_gap(),
                jd=_jd(),
                ai_service=ai,
            )
        )
        self.assertIn("cv_too_short", result.warnings)
        self.assertFalse(result.is_valid)


if __name__ == "__main__":
    unittest.main()
