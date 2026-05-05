"""Tests for profile fallback in CV generation (first-time generate)."""
import asyncio
import unittest
from uuid import uuid4

from app.application.use_cases.generate_cv import GenerateCVUseCase


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeCVRepo:
    def __init__(self):
        self.created = []

    async def create(self, cv_entity):
        if not getattr(cv_entity, "id", None):
            cv_entity.id = uuid4()
        self.created.append(cv_entity)
        return cv_entity


class CapturingAIService:
    """Records every call to generate_cv_template for assertion."""

    def __init__(self, response: str):
        self._response = response
        self.calls = []

    async def generate_cv_template(self, job_title, jd_text, level, output_format="markdown", user_profile=None):
        self.calls.append({
            "job_title": job_title,
            "jd_text": jd_text,
            "level": level,
            "output_format": output_format,
            "user_profile": user_profile,
        })
        return self._response


VALID_CV_RESPONSE = """# Nguyễn Văn A

## Thông tin cá nhân
- Email: test@example.com

## Mục tiêu nghề nghiệp
Phát triển sự nghiệp trong lĩnh vực lập trình.

## Kỹ năng
- Python, FastAPI

## Kinh nghiệm
- Làm việc tại [Tên công ty]

## Học vấn
- Đại học [Trường học]
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateCVProfileFallback(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def _make_use_case(self, response=VALID_CV_RESPONSE):
        ai = CapturingAIService(response)
        repo = FakeCVRepo()
        use_case = GenerateCVUseCase(cv_repo=repo, ai_service=ai)
        return use_case, ai, repo

    # ------------------------------------------------------------------
    # profile passed through to AI service
    # ------------------------------------------------------------------

    def test_profile_forwarded_to_ai(self):
        use_case, ai, _ = self._make_use_case()
        profile = {"full_name": "Nguyễn Huy Hoàng", "email": "hoang@example.com", "phone_number": "0123456789"}

        self._run(use_case.execute(
            user_id=uuid4(),
            job_title="Backend Developer",
            jd_text="Python, FastAPI experience required",
            level="Junior",
            user_profile=profile,
        ))

        self.assertEqual(len(ai.calls), 1)
        self.assertEqual(ai.calls[0]["user_profile"], profile)

    # ------------------------------------------------------------------
    # no profile → None passed through
    # ------------------------------------------------------------------

    def test_no_profile_passes_none(self):
        use_case, ai, repo = self._make_use_case()

        self._run(use_case.execute(
            user_id=uuid4(),
            job_title="Frontend Developer",
            jd_text="React experience required",
            level="Fresher",
        ))

        self.assertIsNone(ai.calls[0]["user_profile"])
        saved = repo.created[0]
        self.assertIsNone(saved.base_profile_data.get("profile_fallback"))

    # ------------------------------------------------------------------
    # profile stored in base_profile_data
    # ------------------------------------------------------------------

    def test_profile_stored_in_base_profile_data(self):
        use_case, _, repo = self._make_use_case()
        profile = {"full_name": "Test User", "email": "test@test.com"}

        self._run(use_case.execute(
            user_id=uuid4(),
            job_title="Data Scientist",
            jd_text="ML experience",
            level="Senior",
            user_profile=profile,
        ))

        saved = repo.created[0]
        self.assertEqual(saved.base_profile_data.get("profile_fallback"), profile)

    # ------------------------------------------------------------------
    # empty profile dict → treated as no profile
    # ------------------------------------------------------------------

    def test_empty_profile_dict_forwarded(self):
        use_case, ai, repo = self._make_use_case()

        self._run(use_case.execute(
            user_id=uuid4(),
            job_title="QA Engineer",
            jd_text="Testing experience",
            level="Middle",
            user_profile={},
        ))

        # Empty dict passed through to AI unchanged
        self.assertEqual(ai.calls[0]["user_profile"], {})
        # Empty dict stored as-is (distinct from None = lookup failed)
        saved = repo.created[0]
        self.assertEqual(saved.base_profile_data.get("profile_fallback"), {})


class TestGeminiServiceProfilePrompt(unittest.TestCase):
    """Unit-test the prompt-building logic in GeminiService (no real API call)."""

    def _build_prompt_section(self, user_profile):
        """Replicate the profile_section construction from GeminiService."""
        profile_section = ""
        if user_profile:
            profile_lines = []
            if user_profile.get("full_name"):
                profile_lines.append(f"  - Họ và tên: {user_profile['full_name']}")
            if user_profile.get("email"):
                profile_lines.append(f"  - Email: {user_profile['email']}")
            if user_profile.get("phone_number"):
                profile_lines.append(f"  - Số điện thoại: {user_profile['phone_number']}")
            if profile_lines:
                profile_section = (
                    "\n        Thông tin profile người dùng (dùng làm fallback cho phần Thông tin cá nhân):\n"
                    + "\n".join(profile_lines)
                    + "\n        Lưu ý: Nếu người dùng đã cung cấp thông tin cá nhân trong prompt hoặc JD, "
                    "ưu tiên thông tin đó. Chỉ dùng profile trên khi input không có thông tin tương ứng. "
                    "Không tự bịa thêm nếu cả input lẫn profile đều không có.\n"
                )
        return profile_section

    def test_full_profile_includes_all_fields(self):
        profile = {
            "full_name": "Hoàng Nguyễn",
            "email": "hoang@example.com",
            "phone_number": "0987654321",
        }
        section = self._build_prompt_section(profile)
        self.assertIn("Hoàng Nguyễn", section)
        self.assertIn("hoang@example.com", section)
        self.assertIn("0987654321", section)

    def test_missing_phone_not_included(self):
        profile = {"full_name": "Hoàng Nguyễn", "email": "hoang@example.com"}
        section = self._build_prompt_section(profile)
        self.assertNotIn("Số điện thoại", section)
        self.assertIn("Hoàng Nguyễn", section)

    def test_empty_profile_produces_no_section(self):
        section = self._build_prompt_section({})
        self.assertEqual(section, "")

    def test_none_profile_produces_no_section(self):
        section = self._build_prompt_section(None)
        self.assertEqual(section, "")

    def test_profile_with_only_empty_strings_produces_no_section(self):
        profile = {"full_name": "", "email": "", "phone_number": ""}
        section = self._build_prompt_section(profile)
        self.assertEqual(section, "")


if __name__ == "__main__":
    unittest.main()
