"""Test double for :class:`IAIService`.

Implements every abstract method so concrete subclasses only override
what they need. ``generate_structured`` is the one method Phase 0 tests
exercise; the rest raise ``NotImplementedError`` so misuse is loud.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from app.application.interfaces.ai_service import IAIService


class FakeIAIService(IAIService):
    """Programmable fake AI service for unit tests.

    Usage:
        fake = FakeIAIService(structured_response={"job_title": "Backend"})
        # or
        fake = FakeIAIService(structured_factory=lambda prompt: {...})

    ``captured_prompts`` records every prompt sent to
    :meth:`generate_structured` so tests can assert the prompt body
    contains specific variables.
    """

    def __init__(
        self,
        *,
        structured_response: Any | None = None,
        structured_factory: Callable[[str], Any] | None = None,
        raise_on_structured: Exception | None = None,
        text_response: str | None = None,
        text_factory: Callable[[str], str] | None = None,
        raise_on_text: Exception | None = None,
    ) -> None:
        self._structured_response = structured_response
        self._structured_factory = structured_factory
        self._raise_on_structured = raise_on_structured
        self._text_response = text_response
        self._text_factory = text_factory
        self._raise_on_text = raise_on_text
        self.captured_prompts: list[str] = []
        self.captured_expect_list: list[bool] = []
        self.captured_text_prompts: list[str] = []

    async def generate_structured(
        self,
        prompt: str,
        *,
        expect_list: bool = False,
    ) -> Any:
        self.captured_prompts.append(prompt)
        self.captured_expect_list.append(expect_list)
        if self._raise_on_structured is not None:
            raise self._raise_on_structured
        if self._structured_factory is not None:
            return self._structured_factory(prompt)
        if self._structured_response is not None:
            return self._structured_response
        return [] if expect_list else {}

    async def generate_text(self, prompt: str) -> str:
        self.captured_text_prompts.append(prompt)
        if self._raise_on_text is not None:
            raise self._raise_on_text
        if self._text_factory is not None:
            return self._text_factory(prompt)
        if self._text_response is not None:
            return self._text_response
        return ""

    # ── legacy / unrelated methods — fail loudly if a test uses them ──
    async def extract_cv_info(self, cv_text: str) -> Dict:
        raise NotImplementedError("FakeIAIService.extract_cv_info not configured")

    async def extract_jd_info(self, jd_text: str) -> Dict:
        raise NotImplementedError("FakeIAIService.extract_jd_info not configured")

    async def classify_document(self, document_text: str, filename: str | None = None) -> Dict:
        raise NotImplementedError("FakeIAIService.classify_document not configured")

    async def rewrite_cv(
        self, cv_text: str, jd_text: str, cv_extracted: Dict, jd_extracted: Dict
    ) -> str:
        raise NotImplementedError("FakeIAIService.rewrite_cv not configured")

    async def check_hallucination(
        self, original_cv: str, rewritten_cv: str, cv_extracted: Dict
    ) -> List[Dict]:
        raise NotImplementedError("FakeIAIService.check_hallucination not configured")

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("FakeIAIService.get_embeddings not configured")

    async def evaluate_jd(self, jd_text: str, jd_extracted: Dict) -> Dict:
        raise NotImplementedError("FakeIAIService.evaluate_jd not configured")

    async def suggest_interview_questions(self, cv_extracted: Dict, jd_extracted: Dict) -> List[Dict]:
        raise NotImplementedError("FakeIAIService.suggest_interview_questions not configured")

    async def negotiate_salary(self, cv_extracted: Dict, jd_extracted: Dict) -> Dict:
        raise NotImplementedError("FakeIAIService.negotiate_salary not configured")

    async def generate_cv_template(
        self,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
        user_profile: Dict | None = None,
    ) -> str:
        raise NotImplementedError("FakeIAIService.generate_cv_template not configured")

    async def chat_interaction(self, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError("FakeIAIService.chat_interaction not configured")

    async def chat_interaction_stream(self, messages: List[Dict[str, str]]):
        raise NotImplementedError("FakeIAIService.chat_interaction_stream not configured")
        yield  # pragma: no cover — make this an async generator

    async def plan_cv_edits(
        self,
        messages: List[Dict[str, str]],
        current_cv: str,
        output_format: str = "markdown",
    ) -> Dict:
        raise NotImplementedError("FakeIAIService.plan_cv_edits not configured")
