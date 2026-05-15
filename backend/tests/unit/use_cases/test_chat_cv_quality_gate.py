"""Regression: chat-gen flow must persist the JD the gate scored against.

Before BE-4 the saved generated CV stored ``target_jd_text="Được cung cấp
qua chat"`` whenever the JD lacked a marker like "JD:" / "Job description"
even though the quality gate had successfully scored against the full JD
body. A subsequent re-analyze (``createAnalysisFromGeneratedCV``) then
ran on a different JD value, leading to scoring drift versus the gate.

This test asserts ``_apply_quality_gate`` returns the resolved JD and
``_build_generated_cv`` writes it into ``target_jd_text``.
"""
from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from app.application.use_cases.chat_cv import ChatCVUseCase
from app.domain.entities.generated_cv import GeneratedCV
from tests.fixtures.fake_ai import FakeIAIService


def _run(coro):
    return asyncio.run(coro)


_REAL_CV_MARKDOWN = """# [Họ và tên]
candidate@example.com

## Mục tiêu nghề nghiệp
Senior Backend Engineer with 5 years building Python and FastAPI services on Docker and PostgreSQL.

## Kỹ năng
- Python, FastAPI, Docker, PostgreSQL

## Kinh nghiệm
**Acme Inc** — Senior Engineer | 2020 - now
- Built FastAPI payments service handling 2 million requests per day on Docker across three regions
- Reduced PostgreSQL p99 latency by 45 percent through index tuning for 14 critical endpoints
- Designed Python microservice contracts adopted by 8 teams within six months of launch

## Học vấn
- B.Sc. Computer Science, [Tên trường], 2018
"""

# Has a JD marker word ("requirements") + ≥120 chars so
# _extract_target_jd_from_messages picks it up and the gate runs.
_JD_WITH_MARKER = (
    "Senior Backend Engineer requirements: 5+ years of Python and FastAPI. "
    "Must have Docker and PostgreSQL expertise. Responsibilities include "
    "API design and database optimisation for high-throughput systems."
)


def _strong_factory() -> Any:
    """LLM responses that make the gate pass on the first analyze."""
    def factory(prompt: str) -> Any:
        lower = prompt.lower()
        if "job description" in lower and "extract structured fields" in lower:
            return {
                "job_title": "Senior Backend Engineer",
                "seniority": "senior",
                "must_have_keywords": ["Python", "FastAPI", "Docker", "PostgreSQL"],
                "nice_to_have_keywords": [],
                "tools": ["Docker"],
                "responsibilities": ["API design", "Database optimisation"],
                "years_of_experience": 5,
                "domain": None,
            }
        if "cv parser" in lower:
            return {
                "summary": (
                    "Senior Backend Engineer with 5 years building Python and FastAPI "
                    "services on Docker and PostgreSQL."
                ),
                "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
                "tools": ["Docker"],
                "experience": [
                    {
                        "role": "Senior Engineer",
                        "company": "Acme Inc",
                        "period": "2020 - now",
                        "bullets": [
                            "Built FastAPI payments service handling 2 million requests per day on Docker across three regions",
                            "Reduced PostgreSQL p99 latency by 45 percent through index tuning for 14 critical endpoints",
                            "Designed Python microservice contracts adopted by 8 teams within six months of launch",
                        ],
                    }
                ],
                "education": ["B.Sc. Computer Science, 2018"],
            }
        if "candidate experience bullets" in lower:
            return {"score": 90, "reason": "stub"}
        if "candidate summary" in lower:
            return {"score": 88, "reason": "stub"}
        return {}

    return factory


class _CapturingRepo:
    """Minimal repo capturing the saved CV's target_jd_text."""

    def __init__(self) -> None:
        self.saved: list[GeneratedCV] = []

    async def create(self, cv: GeneratedCV) -> GeneratedCV:
        # Simulate DB assigning an id.
        if cv.id is None:
            cv.id = uuid4()
        self.saved.append(cv)
        return cv

    async def create_versioned(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
        parent_version_id: UUID,
        target_jd_text: str | None,
        base_profile_data: dict | None,
        generated_content: dict,
        status: str,
    ) -> GeneratedCV:
        cv = GeneratedCV(
            id=uuid4(),
            user_id=user_id,
            conversation_id=conversation_id,
            version=2,
            parent_version_id=parent_version_id,
            target_jd_text=target_jd_text,
            base_profile_data=base_profile_data,
            generated_content=generated_content,
            status=status,
        )
        self.saved.append(cv)
        return cv

    async def save_chat_messages(self, *_args, **_kwargs) -> None:
        return None


def test_quality_gate_threads_jd_into_target_jd_text() -> None:
    """When gate runs successfully, the saved CV's ``target_jd_text``
    should equal the JD body the gate actually scored against, not the
    legacy ``"Được cung cấp qua chat"`` sentinel.

    Before BE-4, ``_apply_quality_gate`` returned only the (possibly
    revised) CV body; ``_build_generated_cv`` then ran the same JD
    extractor against the messages a second time. The two paths
    happened to agree, but there was no single source of truth — any
    drift in the resolver (e.g. trimming, different marker logic)
    would silently desync gate vs persisted JD.
    """
    repo = _CapturingRepo()
    fake = FakeIAIService(structured_factory=_strong_factory())
    use_case = ChatCVUseCase(repo, fake)

    messages = [{"role": "user", "content": _JD_WITH_MARKER}]

    cv_content, resolved_jd = _run(
        use_case._apply_quality_gate(
            cv_content=_REAL_CV_MARKDOWN,
            messages=messages,
            current_cv=None,
            output_format="markdown",
        )
    )

    # Gate found the JD via the "requirements" marker and ran scoring;
    # it returns the JD body it actually used as a single source of truth.
    assert resolved_jd is not None and resolved_jd.strip() == _JD_WITH_MARKER.strip(), (
        f"resolved_jd should be the JD body, got: {resolved_jd!r}"
    )

    payload = _run(
        use_case._build_generated_cv(
            user_id=uuid4(),
            conversation_id=uuid4(),
            messages=messages,
            reply_text="*(Đã tạo CV thành công)*",
            cv_content=cv_content,
            output_format="markdown",
            current_cv=None,
            resolved_jd_text=resolved_jd,
        )
    )

    # New conversation → returned a GeneratedCV entity, not a dict.
    assert isinstance(payload, GeneratedCV)
    assert payload.target_jd_text == _JD_WITH_MARKER.strip()
    assert payload.target_jd_text != "Được cung cấp qua chat"


def test_existing_conversation_upgrades_sentinel_when_new_jd_resolved() -> None:
    """If v1 was saved with the sentinel (no JD signal at the time) and
    a follow-up turn carries a real JD, the new version's
    ``target_jd_text`` should be upgraded to that JD body.

    Pre-BE-4 the new version always inherited ``current_cv.target_jd_text``
    verbatim, so the sentinel persisted forever even after the user
    finally pasted a JD.
    """
    repo = _CapturingRepo()
    fake = FakeIAIService(structured_factory=_strong_factory())
    use_case = ChatCVUseCase(repo, fake)

    parent_cv = GeneratedCV(
        id=uuid4(),
        user_id=uuid4(),
        conversation_id=uuid4(),
        version=1,
        target_jd_text="Được cung cấp qua chat",
        base_profile_data={},
        generated_content={"content": _REAL_CV_MARKDOWN, "format": "markdown"},
        status="completed",
    )
    messages = [{"role": "user", "content": _JD_WITH_MARKER}]

    cv_content, resolved_jd = _run(
        use_case._apply_quality_gate(
            cv_content=_REAL_CV_MARKDOWN,
            messages=messages,
            current_cv=parent_cv,
            output_format="markdown",
        )
    )
    assert resolved_jd is not None

    payload = _run(
        use_case._build_generated_cv(
            user_id=parent_cv.user_id,
            conversation_id=parent_cv.conversation_id,
            messages=messages,
            reply_text="*(Đã tạo CV thành công)*",
            cv_content=cv_content,
            output_format="markdown",
            current_cv=parent_cv,
            resolved_jd_text=resolved_jd,
        )
    )

    assert isinstance(payload, dict)
    assert payload["target_jd_text"] == _JD_WITH_MARKER.strip()
    assert payload["target_jd_text"] != "Được cung cấp qua chat"


def test_quality_gate_skipped_falls_back_to_sentinel() -> None:
    """If the gate is skipped (no JD signal), legacy sentinel is preserved
    so existing FE expectations still hold.
    """
    repo = _CapturingRepo()
    fake = FakeIAIService(structured_factory=_strong_factory())
    use_case = ChatCVUseCase(repo, fake)

    messages_no_jd = [{"role": "user", "content": "Tạo cho mình một CV mẫu nhé"}]

    cv_content, resolved_jd = _run(
        use_case._apply_quality_gate(
            cv_content=_REAL_CV_MARKDOWN,
            messages=messages_no_jd,
            current_cv=None,
            output_format="markdown",
        )
    )
    assert resolved_jd is None  # gate skipped

    payload = _run(
        use_case._build_generated_cv(
            user_id=uuid4(),
            conversation_id=uuid4(),
            messages=messages_no_jd,
            reply_text="*(Đã tạo CV thành công)*",
            cv_content=cv_content,
            output_format="markdown",
            current_cv=None,
            resolved_jd_text=resolved_jd,
        )
    )
    assert isinstance(payload, GeneratedCV)
    assert payload.target_jd_text == "Được cung cấp qua chat"
