"""Phase 0 — JD extractor tests (LLM mocked via FakeIAIService)."""
from __future__ import annotations

import asyncio

from app.application.services.shared.jd_extractor import extract_jd
from tests.fixtures.fake_ai import FakeIAIService


_JD_SAMPLE = (
    "We are hiring a Senior Backend Engineer. "
    "Requirements: 5+ years experience with Python and FastAPI. "
    "Must have PostgreSQL and AWS experience. "
    "Nice to have Redis, Kafka. "
    "Responsibilities include API design and mentoring."
)


def _run(coro):
    return asyncio.run(coro)


class TestExtractJDHappyPath:
    def test_full_jd_returns_populated_schema(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "job_title": "Senior Backend Engineer",
                "seniority": "senior",
                "must_have_keywords": ["Python", "FastAPI", "PostgreSQL", "AWS"],
                "nice_to_have_keywords": ["Redis", "Kafka"],
                "tools": ["Docker"],
                "responsibilities": ["API design", "Mentoring"],
                "years_of_experience": "5+ years",
                "domain": "fintech",
            }
        )
        schema = _run(extract_jd(_JD_SAMPLE, fake))
        assert schema.is_usable is True
        assert schema.job_title == "Senior Backend Engineer"
        assert schema.seniority == "senior"
        # Normalisation should lower-case + alias-collapse the input list.
        assert "python" in schema.must_have_keywords
        assert "fastapi" in schema.must_have_keywords
        assert "postgresql" in schema.must_have_keywords
        assert "docker" in schema.tools
        # YOE extracted from the free-form string.
        assert schema.years_of_experience == 5
        assert schema.extraction_warnings == []

    def test_seniority_synonym_mapped(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "seniority": "Middle",
                "must_have_keywords": ["python"],
            }
        )
        schema = _run(extract_jd(_JD_SAMPLE, fake))
        assert schema.seniority == "mid"


class TestExtractJDFailureModes:
    def test_short_jd_returns_empty_with_warning(self) -> None:
        fake = FakeIAIService(structured_response={"must_have_keywords": ["python"]})
        schema = _run(extract_jd("too short", fake))
        assert schema.extraction_warnings == ["jd_too_short"]
        assert schema.is_usable is False
        # AI service must not be called for a too-short JD.
        assert fake.captured_prompts == []

    def test_empty_payload_returns_empty_with_warning(self) -> None:
        fake = FakeIAIService(structured_response={})
        schema = _run(extract_jd(_JD_SAMPLE, fake))
        assert "jd_extraction_failed" in schema.extraction_warnings

    def test_ai_exception_returns_empty_with_warning(self) -> None:
        fake = FakeIAIService(raise_on_structured=RuntimeError("boom"))
        schema = _run(extract_jd(_JD_SAMPLE, fake))
        assert "jd_extraction_failed" in schema.extraction_warnings

    def test_no_required_skills_flagged(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "must_have_keywords": [],
                "nice_to_have_keywords": ["redis"],
            }
        )
        schema = _run(extract_jd(_JD_SAMPLE, fake))
        assert "no_required_skills_found" in schema.extraction_warnings
        assert schema.is_usable is False


class TestExtractJDNormalisation:
    def test_aliases_collapse_react_variants(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "must_have_keywords": ["React", "React.js", "ReactJS"],
            }
        )
        schema = _run(extract_jd(_JD_SAMPLE, fake))
        # All three collapse to a single "react" token.
        assert schema.must_have_keywords == ["react"]

    def test_responsibilities_capped_at_eight(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "must_have_keywords": ["python"],
                "responsibilities": [f"Resp {i}" for i in range(20)],
            }
        )
        schema = _run(extract_jd(_JD_SAMPLE, fake))
        assert len(schema.responsibilities) == 8


class TestExtractJDPromptInjection:
    def test_jd_text_is_present_in_prompt(self) -> None:
        fake = FakeIAIService(structured_response={"must_have_keywords": ["python"]})
        _run(extract_jd(_JD_SAMPLE, fake))
        assert len(fake.captured_prompts) == 1
        assert "Senior Backend Engineer" in fake.captured_prompts[0]
