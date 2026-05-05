"""Unit tests for :mod:`app.application.services.generation.cv_generator`."""
from __future__ import annotations

import asyncio
import unittest
from typing import Any, Dict, List

from app.application.services.generation import (
    build_profile_section,
    format_guide_for,
    generate_cv,
)
from tests.fixtures.fake_ai import FakeIAIService


class _RecordingAIService(FakeIAIService):
    """Captures the kwargs passed to ``generate_cv_template``."""

    def __init__(self, response: str = "", *, raises: Exception | None = None) -> None:
        super().__init__()
        self._response = response
        self._raises = raises
        self.calls: List[Dict[str, Any]] = []

    async def generate_cv_template(
        self,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
        user_profile: Dict | None = None,
    ) -> str:
        self.calls.append(
            {
                "job_title": job_title,
                "jd_text": jd_text,
                "level": level,
                "output_format": output_format,
                "user_profile": user_profile,
            }
        )
        if self._raises is not None:
            raise self._raises
        return self._response


_PERSONALIZED_CV = """# Nguyễn Văn A

## Thông tin cá nhân
- Email: nva@example.com

## Mục tiêu nghề nghiệp
Phát triển sự nghiệp Backend.

## Kỹ năng
- Python, FastAPI

## Kinh nghiệm
- Phát triển hệ thống tại Acme Corp năm 2024.

## Học vấn
- Đại học Bách Khoa
"""

_TEMPLATE_CV = """# [Họ và tên]

## Thông tin cá nhân
- Email: [Email]
- SĐT: [Số điện thoại]

## Kỹ năng
- [Kỹ năng 1]

## Kinh nghiệm
- Làm việc tại [Tên công ty] năm [Năm]
"""


def _run(coro):
    return asyncio.run(coro)


class TestBuildProfileSection(unittest.TestCase):
    def test_none_yields_empty(self) -> None:
        self.assertEqual(build_profile_section(None), "")

    def test_empty_dict_yields_empty(self) -> None:
        self.assertEqual(build_profile_section({}), "")

    def test_blank_fields_yield_empty(self) -> None:
        self.assertEqual(
            build_profile_section({"full_name": "", "email": "  ", "phone_number": None}),
            "",
        )

    def test_full_profile_includes_all_fields(self) -> None:
        section = build_profile_section(
            {
                "full_name": "Hoàng Nguyễn",
                "email": "hoang@example.com",
                "phone_number": "0987654321",
            }
        )
        self.assertIn("Hoàng Nguyễn", section)
        self.assertIn("hoang@example.com", section)
        self.assertIn("0987654321", section)

    def test_partial_profile_skips_missing(self) -> None:
        section = build_profile_section(
            {"full_name": "Hoàng Nguyễn", "email": "hoang@example.com"}
        )
        self.assertIn("Hoàng Nguyễn", section)
        self.assertNotIn("Số điện thoại", section)


class TestFormatGuideFor(unittest.TestCase):
    def test_markdown_and_docx_have_distinct_guides(self) -> None:
        self.assertNotEqual(format_guide_for("markdown"), format_guide_for("docx"))

    def test_unknown_format_falls_back(self) -> None:
        self.assertTrue(format_guide_for("html").startswith("tuân thủ markdown"))


class TestGenerateCV(unittest.TestCase):
    def test_personalized_when_no_placeholders(self) -> None:
        ai = _RecordingAIService(_PERSONALIZED_CV)
        result = _run(
            generate_cv(
                job_title="Backend Developer",
                jd_text="Python, FastAPI",
                level="Junior",
                ai_service=ai,
                user_profile={"full_name": "Nguyễn Văn A", "email": "nva@example.com"},
            )
        )

        self.assertEqual(result.generation_mode, "personalized")
        self.assertEqual(result.placeholders_remaining, 0)
        self.assertTrue(result.candidate_facts_present)
        self.assertEqual(result.warnings, [])
        self.assertTrue(result.is_valid)

    def test_template_only_when_placeholders_remain(self) -> None:
        ai = _RecordingAIService(_TEMPLATE_CV)
        result = _run(
            generate_cv(
                job_title="Backend Developer",
                jd_text="Python, FastAPI",
                level="Fresher",
                ai_service=ai,
            )
        )
        self.assertEqual(result.generation_mode, "template_only")
        self.assertGreater(result.placeholders_remaining, 0)
        self.assertFalse(result.candidate_facts_present)

    def test_user_profile_forwarded_verbatim(self) -> None:
        ai = _RecordingAIService(_PERSONALIZED_CV)
        profile = {"full_name": "Test User", "email": "t@t.com"}
        _run(
            generate_cv(
                job_title="QA",
                jd_text="testing",
                level="Senior",
                ai_service=ai,
                user_profile=profile,
            )
        )
        self.assertEqual(ai.calls[0]["user_profile"], profile)
        # Mutating after the call must not mutate the AI service capture —
        # generator copies before forwarding.
        profile["full_name"] = "Mutated"
        self.assertEqual(ai.calls[0]["user_profile"]["full_name"], "Test User")

    def test_ai_failure_returns_empty_with_warning(self) -> None:
        ai = _RecordingAIService(raises=RuntimeError("provider down"))
        result = _run(
            generate_cv(
                job_title="Data Scientist",
                jd_text="ML",
                level="Senior",
                ai_service=ai,
            )
        )
        self.assertEqual(result.content, "")
        self.assertIn("ai_provider_failed", result.warnings)
        self.assertIn("ai_returned_empty", result.warnings)
        self.assertFalse(result.is_valid)

    def test_short_response_flagged(self) -> None:
        ai = _RecordingAIService("# tiny\n")
        result = _run(
            generate_cv(
                job_title="Backend",
                jd_text="Python",
                level="Junior",
                ai_service=ai,
            )
        )
        self.assertIn("cv_too_short", result.warnings)
        self.assertFalse(result.is_valid)


if __name__ == "__main__":
    unittest.main()
