"""Streaming variant: :func:`run_improvement_loop_events`.

The non-streaming run is already exercised in
``test_improvement_loop.py``; here we only verify that the streaming
generator emits the right event sequence + that the final ``done``
payload matches the eager call.
"""
from __future__ import annotations

import asyncio
import unittest

from app.application.services.generation import (
    LoopOutcome,
    run_improvement_loop,
    run_improvement_loop_events,
)
from tests.unit.services.test_improvement_loop import (
    _LoopFakeAI,
    _REAL_CV_BODY,
    _build_structured_factory,
    _cv_payload_weak,
)


def _run(coro):
    return asyncio.run(coro)


async def _collect(gen):
    events: list[tuple[str, object]] = []
    async for kind, payload in gen:
        events.append((kind, payload))
    return events


_JD_TEXT = (
    "We need a senior backend engineer with Python, FastAPI, Docker. "
    "Responsibilities include API design and database optimisation."
)


class TestStreamingEventSequence(unittest.TestCase):
    def test_emits_iteration_then_done_on_pass(self) -> None:
        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            structured_factory=_build_structured_factory(rel=90, summ=85),
        )
        events = _run(
            _collect(
                run_improvement_loop_events(
                    job_title="Backend Engineer",
                    jd_text=_JD_TEXT,
                    level="Senior",
                    ai_service=ai,
                    max_iterations=3,
                )
            )
        )
        kinds = [k for k, _ in events]
        # exactly one iteration event then a done event (PASS short-circuits).
        self.assertEqual(kinds, ["iteration", "done"])
        outcome = events[-1][1]
        self.assertIsInstance(outcome, LoopOutcome)
        self.assertEqual(outcome.stopped_reason, "passed_threshold")

    def test_emits_one_done_when_jd_unusable(self) -> None:
        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            structured_factory=lambda prompt: {},  # JD parse fails
        )
        events = _run(
            _collect(
                run_improvement_loop_events(
                    job_title="Backend Engineer",
                    jd_text=_JD_TEXT,
                    level="Senior",
                    ai_service=ai,
                    max_iterations=3,
                )
            )
        )
        kinds = [k for k, _ in events]
        # No iterations at all when JD fails — single done event.
        self.assertEqual(kinds, ["done"])
        self.assertEqual(events[0][1].stopped_reason, "insufficient_jd")

    def test_emits_multiple_iterations_until_no_improvement(self) -> None:
        ai = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            revise_responses=[_REAL_CV_BODY],
            structured_factory=_build_structured_factory(
                rel=55, summ=55, cv=_cv_payload_weak,
            ),
        )
        events = _run(
            _collect(
                run_improvement_loop_events(
                    job_title="Backend Engineer",
                    jd_text=_JD_TEXT,
                    level="Senior",
                    ai_service=ai,
                    max_iterations=4,
                )
            )
        )
        kinds = [k for k, _ in events]
        # two iteration events then done.
        self.assertEqual(kinds, ["iteration", "iteration", "done"])
        self.assertEqual(events[-1][1].stopped_reason, "no_improvement")

    def test_drained_stream_matches_eager_run(self) -> None:
        """Streaming and eager wrappers must reach the same outcome."""
        ai_stream = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            structured_factory=_build_structured_factory(rel=90, summ=85),
        )
        ai_eager = _LoopFakeAI(
            gen_response=_REAL_CV_BODY,
            structured_factory=_build_structured_factory(rel=90, summ=85),
        )

        events = _run(
            _collect(
                run_improvement_loop_events(
                    job_title="Backend Engineer",
                    jd_text=_JD_TEXT,
                    level="Senior",
                    ai_service=ai_stream,
                    max_iterations=3,
                )
            )
        )
        stream_outcome: LoopOutcome = events[-1][1]
        eager_outcome = _run(
            run_improvement_loop(
                job_title="Backend Engineer",
                jd_text=_JD_TEXT,
                level="Senior",
                ai_service=ai_eager,
                max_iterations=3,
            )
        )
        self.assertEqual(stream_outcome.stopped_reason, eager_outcome.stopped_reason)
        self.assertEqual(stream_outcome.best_index, eager_outcome.best_index)
        self.assertEqual(
            len(stream_outcome.iterations), len(eager_outcome.iterations)
        )


if __name__ == "__main__":
    unittest.main()
