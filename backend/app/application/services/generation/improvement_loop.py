"""Improvement loop — Phase 3 entry point.

Glue between Phase 2's generator + Phase 1's analyzer:

    generate → analyze → (if not PASS) revise → analyze → …

Each loop step records an :class:`IterationRecord` so the caller can
persist the trail. Stop conditions follow the canonical
:data:`app.domain.schemas.iteration_schema.StoppedReason` literal.

Two surfaces:

* :func:`run_improvement_loop` — runs the whole loop and returns the
  final :class:`LoopOutcome` once it stops.
* :func:`run_improvement_loop_events` — async generator yielding a
  ``"iteration"`` event after each step and a final ``"done"`` event
  carrying the :class:`LoopOutcome`. The SSE route uses this so the
  frontend can render progress in real time.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Mapping, Tuple

from app.application.interfaces.ai_service import IAIService
from app.application.services.generation.cv_generator import (
    GenerationOutput,
    generate_cv,
)
from app.application.services.generation.cv_reviser import (
    RevisionOutput,
    revise_cv,
)
from app.application.services.scoring import score_cv
from app.application.services.shared import extract_cv, extract_jd
from app.domain.schemas import (
    AnalysisResultSchema,
    GapAnalysis,
    JDSchema,
    PASS_THRESHOLD,
    StoppedReason,
)
from app.logger import get_logger

logger = get_logger("app.application.services.generation.improvement_loop")

DEFAULT_MAX_ITERATIONS = 3
MIN_IMPROVEMENT_DELTA = 0.5  # below this we treat the run as plateaued


@dataclass(frozen=True)
class _IterationData:
    """Internal per-iteration trace used to build IterationRecord later.

    Kept private; the use case translates these into
    :class:`app.domain.schemas.IterationRecord` once cv_ids are known.
    """

    iteration_index: int
    overall_score: float | None
    verdict: str | None
    gap_analysis: GapAnalysis | None
    latency_ms: float
    content: str
    analysis: AnalysisResultSchema | None
    placeholders_remaining: int
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LoopOutcome:
    """Aggregate of one ``run_improvement_loop`` invocation.

    ``best_content`` is the markdown the use case persists. ``best_index``
    points back into ``iterations`` so the use case can stamp the matching
    record with the resulting cv_id.
    """

    best_index: int
    best_content: str
    best_analysis: AnalysisResultSchema | None
    iterations: list[_IterationData]
    stopped_reason: StoppedReason
    jd: JDSchema | None


async def _run_iteration(
    *,
    iteration_index: int,
    is_first: bool,
    current_cv: str,
    previous_gap: GapAnalysis | None,
    previous_missing_keywords: list[str],
    job_title: str,
    jd_text: str,
    level: str,
    jd: JDSchema,
    ai_service: IAIService,
    user_profile: Mapping[str, object] | None,
    output_format: str,
    is_final: bool,
) -> _IterationData:
    """One full step: (generate or revise) → extract → score."""
    start = time.perf_counter()

    if is_first:
        gen: GenerationOutput = await generate_cv(
            job_title=job_title,
            jd_text=jd_text,
            level=level,
            ai_service=ai_service,
            output_format=output_format,
            user_profile=user_profile,
        )
        content = gen.content
        warnings = list(gen.warnings)
        placeholders_remaining = gen.placeholders_remaining
    else:
        assert previous_gap is not None  # only the first iteration has no prior gap
        rev: RevisionOutput = await revise_cv(
            current_cv=current_cv,
            gap=previous_gap,
            jd=jd,
            ai_service=ai_service,
            job_title=job_title,
            level=level,
            missing_keywords=previous_missing_keywords,
            output_format=output_format,
        )
        content = rev.content
        warnings = list(rev.warnings)
        placeholders_remaining = rev.placeholders_remaining

    if not content:
        latency_ms = (time.perf_counter() - start) * 1000
        return _IterationData(
            iteration_index=iteration_index,
            overall_score=None,
            verdict=None,
            gap_analysis=None,
            latency_ms=latency_ms,
            content="",
            analysis=None,
            placeholders_remaining=placeholders_remaining,
            warnings=warnings,
        )

    cv_schema = await extract_cv(content, ai_service)
    analysis = await score_cv(
        cv_schema,
        jd,
        ai_service,
        analysis_meta={"source": "improvement_loop", "iteration": iteration_index},
        enable_suggestions=is_final,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    return _IterationData(
        iteration_index=iteration_index,
        overall_score=analysis.overall_score,
        verdict=analysis.verdict,
        gap_analysis=analysis.gap_analysis,
        latency_ms=latency_ms,
        content=content,
        analysis=analysis,
        placeholders_remaining=placeholders_remaining,
        warnings=warnings,
    )


async def run_improvement_loop_events(
    *,
    job_title: str,
    jd_text: str,
    level: str,
    ai_service: IAIService,
    output_format: str = "markdown",
    user_profile: Mapping[str, object] | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    pass_threshold: float = PASS_THRESHOLD,
) -> AsyncIterator[Tuple[str, object]]:
    """Streaming variant — yields events as the loop progresses.

    Event shapes::

        ("iteration", _IterationData)   # emitted after each step
        ("done", LoopOutcome)           # final event before generator stops

    The non-streaming :func:`run_improvement_loop` drains this generator
    so behaviour (stop conditions, scoring) is identical.
    """
    # JD extraction is shared across all iterations — do it once.
    jd = await extract_jd(jd_text, ai_service)
    if not jd.is_usable:
        outcome = LoopOutcome(
            best_index=-1,
            best_content="",
            best_analysis=None,
            iterations=[],
            stopped_reason="insufficient_jd",
            jd=jd,
        )
        yield "done", outcome
        return

    iterations: list[_IterationData] = []
    current_cv = ""
    previous_gap: GapAnalysis | None = None
    previous_missing: list[str] = []

    best_index = -1
    best_score = -1.0
    best_content = ""
    best_analysis: AnalysisResultSchema | None = None
    stopped: StoppedReason = "max_iterations"

    cap = max(1, max_iterations)
    for i in range(cap):
        is_final = i == cap - 1
        data = await _run_iteration(
            iteration_index=i,
            is_first=(i == 0),
            current_cv=current_cv,
            previous_gap=previous_gap,
            previous_missing_keywords=previous_missing,
            job_title=job_title,
            jd_text=jd_text,
            level=level,
            jd=jd,
            ai_service=ai_service,
            user_profile=user_profile,
            output_format=output_format,
            is_final=is_final,
        )
        iterations.append(data)
        yield "iteration", data

        if data.analysis is None or not data.content:
            stopped = "extractor_failed"
            break

        score = data.overall_score or 0.0
        if score > best_score:
            best_score = score
            best_index = data.iteration_index
            best_content = data.content
            best_analysis = data.analysis

        if (data.overall_score or 0.0) >= pass_threshold:
            stopped = "passed_threshold"
            break

        if i > 0:
            prev = iterations[i - 1]
            if (
                prev.overall_score is not None
                and data.overall_score is not None
                and data.overall_score <= prev.overall_score + MIN_IMPROVEMENT_DELTA
            ):
                stopped = "no_improvement"
                break

        current_cv = data.content
        previous_gap = data.gap_analysis
        previous_missing = list(data.analysis.keyword_report.missing)

    logger.info(
        "improvement_loop: iters=%d best_idx=%d best_score=%.1f stopped=%s",
        len(iterations),
        best_index,
        best_score if best_index >= 0 else 0.0,
        stopped,
    )
    yield "done", LoopOutcome(
        best_index=best_index,
        best_content=best_content,
        best_analysis=best_analysis,
        iterations=iterations,
        stopped_reason=stopped,
        jd=jd,
    )


async def run_improvement_loop(
    *,
    job_title: str,
    jd_text: str,
    level: str,
    ai_service: IAIService,
    output_format: str = "markdown",
    user_profile: Mapping[str, object] | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    pass_threshold: float = PASS_THRESHOLD,
) -> LoopOutcome:
    """Run the generate → analyze → revise loop and return the outcome.

    Thin wrapper over :func:`run_improvement_loop_events` — drains the
    stream and returns only the final ``LoopOutcome``.
    """
    final: LoopOutcome | None = None
    async for kind, payload in run_improvement_loop_events(
        job_title=job_title,
        jd_text=jd_text,
        level=level,
        ai_service=ai_service,
        output_format=output_format,
        user_profile=user_profile,
        max_iterations=max_iterations,
        pass_threshold=pass_threshold,
    ):
        if kind == "done":
            final = payload  # type: ignore[assignment]
    assert final is not None  # generator always yields "done" exactly once
    return final


__all__ = [
    "DEFAULT_MAX_ITERATIONS",
    "LoopOutcome",
    "run_improvement_loop",
    "run_improvement_loop_events",
]
