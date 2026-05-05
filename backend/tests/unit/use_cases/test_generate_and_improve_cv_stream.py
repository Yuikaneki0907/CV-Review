"""Verify GenerateAndImproveCVUseCase.execute_stream emits well-formed SSE.

Exercises both happy path (loop_start → iteration_done* → loop_done) and
JD-failure path (loop_start → loop_error).
"""
from __future__ import annotations

import asyncio
import json
import re
import unittest
from uuid import UUID, uuid4

from app.application.use_cases.generate_and_improve_cv import (
    GenerateAndImproveCVUseCase,
)
from tests.unit.services.test_improvement_loop import (
    _LoopFakeAI,
    _REAL_CV_BODY,
    _build_structured_factory,
)


def _run(coro):
    return asyncio.run(coro)


class _InMemoryCVRepo:
    def __init__(self) -> None:
        self.created = []

    async def create(self, cv_entity):
        if not getattr(cv_entity, "id", None):
            cv_entity.id = uuid4()
        self.created.append(cv_entity)
        return cv_entity


_SSE_RE = re.compile(r"event: (?P<event>\S+)\ndata: (?P<data>.+?)\n\n", flags=re.S)


def _parse_sse(chunks: list[str]) -> list[tuple[str, dict]]:
    parsed: list[tuple[str, dict]] = []
    for chunk in chunks:
        match = _SSE_RE.match(chunk)
        assert match is not None, f"Malformed SSE chunk: {chunk!r}"
        parsed.append((match.group("event"), json.loads(match.group("data"))))
    return parsed


async def _drain_stream(use_case, **kwargs) -> list[str]:
    chunks: list[str] = []
    async for chunk in use_case.execute_stream(**kwargs):
        chunks.append(chunk)
    return chunks


_JD_TEXT = (
    "We need a senior backend engineer with Python, FastAPI, Docker. "
    "Responsibilities include API design and database optimisation."
)


class TestExecuteStreamHappyPath(unittest.TestCase):
    def test_passing_run_emits_loop_done_with_cv_id(self) -> None:
        repo = _InMemoryCVRepo()
        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            structured_factory=_build_structured_factory(rel=90, summ=85),
        )
        use_case = GenerateAndImproveCVUseCase(repo, ai)

        chunks = _run(
            _drain_stream(
                use_case,
                user_id=uuid4(),
                job_title="Backend Engineer",
                jd_text=_JD_TEXT,
                level="Senior",
                max_iterations=3,
            )
        )
        events = _parse_sse(chunks)
        kinds = [name for name, _ in events]
        self.assertEqual(kinds[0], "loop_start")
        self.assertIn("iteration_done", kinds)
        self.assertEqual(kinds[-1], "loop_done")

        final = events[-1][1]
        self.assertEqual(final["stopped_reason"], "passed_threshold")
        # cv_id is a stringified UUID.
        UUID(final["cv_id"])
        # repo has exactly one persisted CV.
        self.assertEqual(len(repo.created), 1)
        self.assertEqual(str(repo.created[0].id), final["cv_id"])


class TestExecuteStreamFailureModes(unittest.TestCase):
    def test_jd_failure_emits_loop_error_without_persisting(self) -> None:
        repo = _InMemoryCVRepo()
        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            structured_factory=lambda prompt: {},  # JD parse fails
        )
        use_case = GenerateAndImproveCVUseCase(repo, ai)

        chunks = _run(
            _drain_stream(
                use_case,
                user_id=uuid4(),
                job_title="Backend Engineer",
                jd_text=_JD_TEXT,
                level="Senior",
                max_iterations=3,
            )
        )
        events = _parse_sse(chunks)
        kinds = [name for name, _ in events]
        self.assertEqual(kinds[0], "loop_start")
        self.assertEqual(kinds[-1], "loop_error")
        # No CV persisted on failure.
        self.assertEqual(repo.created, [])


if __name__ == "__main__":
    unittest.main()
