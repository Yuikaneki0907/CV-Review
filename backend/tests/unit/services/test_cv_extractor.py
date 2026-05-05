"""Phase 0 — CV extractor tests (LLM mocked via FakeIAIService)."""
from __future__ import annotations

import asyncio

from app.application.services.shared.cv_extractor import extract_cv
from tests.fixtures.fake_ai import FakeIAIService


_REAL_CV = """# Nguyễn A
Email: candidate@example.com | GitHub: github.com/nguyena

## Summary
Senior backend engineer with 5 years building distributed services.

## Skills
Python, FastAPI, PostgreSQL, Docker

## Experience
**Acme Inc** — Senior Engineer | 2022 - now
- Built a payments API handling 2M requests/day
- Reduced p99 latency by 40% through query optimisation
- Led migration from MongoDB to PostgreSQL

## Education
B.Sc. Computer Science, HUST 2018
"""

_PLACEHOLDER_CV = """# [Họ và tên]
[Email] | [Số điện thoại]

## Mục tiêu nghề nghiệp
[Mục tiêu nghề nghiệp]

## Kỹ năng
- [Kỹ năng 1]
- [Kỹ năng 2]

## Kinh nghiệm
- Làm việc tại [Tên công ty] [Năm bắt đầu] - [Năm kết thúc]
"""


def _run(coro):
    return asyncio.run(coro)


def _real_cv_payload() -> dict:
    return {
        "summary": "Senior backend engineer with 5 years building distributed services.",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "tools": ["Docker"],
        "experience": [
            {
                "role": "Senior Engineer",
                "company": "Acme Inc",
                "period": "2022 - now",
                "bullets": [
                    "Built a payments API handling 2M requests/day",
                    "Reduced p99 latency by 40% through query optimisation",
                    "Led migration from MongoDB to PostgreSQL",
                ],
            }
        ],
        "education": ["B.Sc. Computer Science, HUST 2018"],
    }


class TestExtractCVHappyPath:
    def test_real_cv_populates_schema(self) -> None:
        fake = FakeIAIService(structured_response=_real_cv_payload())
        schema = _run(extract_cv(_REAL_CV, fake))

        assert schema.candidate_facts_present is True
        assert schema.placeholders_remaining == 0
        assert schema.is_template_only is False
        # Skill normalisation lowercases everything.
        assert "python" in schema.skills
        assert "fastapi" in schema.skills
        assert "postgresql" in schema.skills
        assert len(schema.experience) == 1
        assert schema.experience[0].company == "Acme Inc"
        # Bullets have deterministic tags.
        bullets = schema.experience[0].bullets
        assert any(b.has_action_verb and b.has_metric for b in bullets), (
            "expected at least one bullet with both action verb and metric, got: "
            f"{[(b.text, b.has_action_verb, b.has_metric) for b in bullets]}"
        )

    def test_summary_extracted(self) -> None:
        fake = FakeIAIService(structured_response=_real_cv_payload())
        schema = _run(extract_cv(_REAL_CV, fake))
        assert "Senior backend engineer" in schema.summary


class TestExtractCVPlaceholders:
    def test_placeholder_only_cv_flagged_as_template(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "summary": "",
                "skills": [],
                "tools": [],
                "experience": [],
                "education": [],
            }
        )
        schema = _run(extract_cv(_PLACEHOLDER_CV, fake))
        assert schema.placeholders_remaining > 5
        assert schema.candidate_facts_present is False
        assert schema.is_template_only is True
        assert "many_placeholders" in schema.extraction_warnings

    def test_strip_mode_removes_placeholders_from_prompt(self) -> None:
        fake = FakeIAIService(structured_response={"skills": []})
        _run(extract_cv(_PLACEHOLDER_CV, fake, placeholder_handling="strip"))
        prompt = fake.captured_prompts[0]
        # Assert on placeholders that appear only in the CV body, not in
        # the prompt template's own example instructions ("[Tên công ty]",
        # "<TBD>" are baked into cv_extraction.txt as examples).
        assert "[Họ và tên]" not in prompt
        assert "[Số điện thoại]" not in prompt
        assert "[Năm bắt đầu]" not in prompt

    def test_reject_mode_short_circuits_without_ai_call(self) -> None:
        fake = FakeIAIService(structured_response={"skills": []})
        schema = _run(
            extract_cv(_PLACEHOLDER_CV, fake, placeholder_handling="reject")
        )
        assert schema.extraction_warnings == ["too_many_placeholders"]
        # AI must not be called when the placeholder gate trips.
        assert fake.captured_prompts == []


class TestExtractCVFailureModes:
    def test_short_cv_returns_empty(self) -> None:
        fake = FakeIAIService(structured_response={"skills": ["x"]})
        schema = _run(extract_cv("too short", fake))
        assert schema.extraction_warnings == ["cv_too_short"]
        # AI not called for too-short input.
        assert fake.captured_prompts == []

    def test_ai_failure_falls_back_to_partial_schema(self) -> None:
        fake = FakeIAIService(raise_on_structured=RuntimeError("nope"))
        schema = _run(extract_cv(_REAL_CV, fake))
        # AI failed but raw text had an email — so facts still detected.
        assert "cv_extraction_failed" in schema.extraction_warnings
        assert schema.candidate_facts_present is True


class TestExtractCVBulletTagging:
    def test_action_verb_detected_english(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "skills": ["x"],
                "experience": [
                    {
                        "role": "Eng",
                        "company": "Acme",
                        "period": "2022",
                        "bullets": [
                            "Built a new service from scratch",
                            "Worked on some stuff",
                        ],
                    }
                ],
            }
        )
        schema = _run(extract_cv(_REAL_CV, fake))
        bullets = schema.experience[0].bullets
        assert bullets[0].has_action_verb is True
        assert bullets[1].has_action_verb is False

    def test_action_verb_detected_vietnamese(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "skills": ["x"],
                "experience": [
                    {
                        "role": "Eng",
                        "company": "Acme",
                        "period": "2022",
                        "bullets": [
                            "Phát triển hệ thống thanh toán",
                            "Tham gia dự án",
                        ],
                    }
                ],
            }
        )
        schema = _run(extract_cv(_REAL_CV, fake))
        bullets = schema.experience[0].bullets
        assert bullets[0].has_action_verb is True
        assert bullets[1].has_action_verb is False

    def test_metric_detected(self) -> None:
        fake = FakeIAIService(
            structured_response={
                "skills": ["x"],
                "experience": [
                    {
                        "role": "Eng",
                        "company": "Acme",
                        "period": "2022",
                        "bullets": [
                            "Improved latency by 40%",
                            "Reduced cost 2x",
                            "Joined the team",
                            "Started in 2024",  # bare year — must NOT count as metric
                        ],
                    }
                ],
            }
        )
        schema = _run(extract_cv(_REAL_CV, fake))
        bullets = schema.experience[0].bullets
        assert bullets[0].has_metric is True
        assert bullets[1].has_metric is True
        assert bullets[2].has_metric is False
        assert bullets[3].has_metric is False
