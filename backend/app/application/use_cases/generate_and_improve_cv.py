"""GenerateAndImproveCVUseCase — Phase 3 entry point.

Runs the generate → analyze → revise loop and persists the best CV.
The intermediate iteration trail is embedded in
``generated_content["iterations"]`` so the frontend can show the
improvement curve without a schema migration.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Mapping
from uuid import UUID

from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.repositories import IGeneratedCVRepository
from app.application.services.generation import (
    DEFAULT_MAX_ITERATIONS,
    LoopOutcome,
    run_improvement_loop,
    run_improvement_loop_events,
)
from app.application.use_cases.generate_cv import _looks_like_cv_template
from app.domain.entities.generated_cv import GeneratedCV
from app.domain.schemas import IterationRecord
from app.domain.schemas.cv_schema import PLACEHOLDER_PATTERN
from app.logger import get_logger

logger = get_logger("app.application.use_cases.generate_and_improve_cv")


def _iteration_to_dict(data) -> dict:
    """Serialise an _IterationData into a JSON-safe dict."""
    return {
        "iteration_index": data.iteration_index,
        "overall_score": data.overall_score,
        "verdict": data.verdict,
        "latency_ms": round(data.latency_ms, 1),
        "placeholders_remaining": data.placeholders_remaining,
        "warnings": list(data.warnings),
        "gap_analysis": (
            data.gap_analysis.model_dump() if data.gap_analysis else None
        ),
    }


class GenerateAndImproveCVUseCase:
    """Orchestrator for Phase 3's iterative CV improvement."""

    def __init__(
        self,
        cv_repo: IGeneratedCVRepository,
        ai_service: IAIService,
    ) -> None:
        self._cv_repo = cv_repo
        self._ai_service = ai_service

    async def execute(
        self,
        user_id: UUID,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
        user_profile: Mapping[str, object] | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> GeneratedCV:
        """Run the loop and save the best-scoring CV.

        Raises:
            ValueError: When the loop produced no usable CV (e.g. JD
                unparseable, every iteration failed extraction).
        """
        logger.info(
            "ImproveCV start: user_id=%s job_title=%s level=%s max_iterations=%d has_profile=%s",
            user_id,
            job_title,
            level,
            max_iterations,
            user_profile is not None,
        )

        outcome: LoopOutcome = await run_improvement_loop(
            job_title=job_title,
            jd_text=jd_text,
            level=level,
            ai_service=self._ai_service,
            output_format=output_format,
            user_profile=user_profile,
            max_iterations=max_iterations,
        )

        if not outcome.best_content or not _looks_like_cv_template(outcome.best_content):
            logger.warning(
                "ImproveCV produced no usable CV: stopped=%s iters=%d",
                outcome.stopped_reason,
                len(outcome.iterations),
            )
            raise ValueError(
                f"Quá trình cải thiện CV không tạo được nội dung hợp lệ (lý do: {outcome.stopped_reason})."
            )

        placeholder_count = len(PLACEHOLDER_PATTERN.findall(outcome.best_content))
        generation_mode = "personalized" if placeholder_count == 0 else "template_only"

        iteration_dicts = [_iteration_to_dict(data) for data in outcome.iterations]

        base_profile_data: dict = {
            "job_title": job_title,
            "level": level,
            "generation_mode": generation_mode,
            "candidate_facts": dict(user_profile) if user_profile else {},
            "stopped_reason": outcome.stopped_reason,
            "best_iteration_index": outcome.best_index,
            "iteration_count": len(outcome.iterations),
        }
        if user_profile is not None:
            base_profile_data["profile_fallback"] = dict(user_profile)

        generated_content: dict = {
            "content": outcome.best_content,
            "format": output_format,
            "markdown": outcome.best_content,
            "generation_mode": generation_mode,
            "placeholder_count": placeholder_count,
            "source_jd_text": jd_text,
            "candidate_facts": dict(user_profile) if user_profile else {},
            "iterations": iteration_dicts,
            "best_iteration_index": outcome.best_index,
            "stopped_reason": outcome.stopped_reason,
        }
        if outcome.best_analysis is not None:
            generated_content["best_analysis"] = outcome.best_analysis.model_dump()

        cv_entity = GeneratedCV(
            user_id=user_id,
            target_jd_text=jd_text,
            base_profile_data=base_profile_data,
            generated_content=generated_content,
            status="completed",
        )
        saved_cv = await self._cv_repo.create(cv_entity)

        # Mirror the persisted cv_id back onto the best iteration record —
        # frontend reads this to highlight which row produced the saved CV.
        for entry in generated_content["iterations"]:
            if entry["iteration_index"] == outcome.best_index:
                entry["cv_id"] = str(saved_cv.id)

        logger.info(
            "ImproveCV saved: cv_id=%s best_idx=%d best_score=%.1f stopped=%s iters=%d",
            saved_cv.id,
            outcome.best_index,
            (outcome.best_analysis.overall_score if outcome.best_analysis else 0.0),
            outcome.stopped_reason,
            len(outcome.iterations),
        )
        return saved_cv

    async def execute_stream(
        self,
        user_id: UUID,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
        user_profile: Mapping[str, object] | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> AsyncIterator[str]:
        """Stream SSE-formatted events as the loop runs.

        Event sequence::

            event: loop_start      data: {max_iterations, has_profile}
            event: iteration_done  data: {iteration_index, overall_score, ...}
            event: iteration_done  data: {...}
            event: loop_done       data: {cv_id, best_iteration_index,
                                         stopped_reason, overall_score}
            (or)
            event: loop_error      data: {error: "..."}
        """

        def _sse(event: str, data: object) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

        logger.info(
            "ImproveCV stream start: user_id=%s job_title=%s level=%s max_iterations=%d",
            user_id,
            job_title,
            level,
            max_iterations,
        )

        yield _sse(
            "loop_start",
            {
                "max_iterations": max_iterations,
                "has_profile": user_profile is not None,
                "job_title": job_title,
                "level": level,
            },
        )

        outcome: LoopOutcome | None = None
        try:
            async for kind, payload in run_improvement_loop_events(
                job_title=job_title,
                jd_text=jd_text,
                level=level,
                ai_service=self._ai_service,
                output_format=output_format,
                user_profile=user_profile,
                max_iterations=max_iterations,
            ):
                if kind == "iteration":
                    yield _sse("iteration_done", _iteration_to_dict(payload))
                elif kind == "done":
                    outcome = payload  # type: ignore[assignment]
        except Exception as exc:
            logger.error("ImproveCV stream FAILED: %s", exc, exc_info=True)
            yield _sse("loop_error", {"error": str(exc)})
            return

        if outcome is None or not outcome.best_content or not _looks_like_cv_template(outcome.best_content):
            reason = outcome.stopped_reason if outcome else "unknown"
            yield _sse(
                "loop_error",
                {"error": f"Không tạo được CV hợp lệ (lý do: {reason})"},
            )
            return

        placeholder_count = len(PLACEHOLDER_PATTERN.findall(outcome.best_content))
        generation_mode = "personalized" if placeholder_count == 0 else "template_only"
        iteration_dicts = [_iteration_to_dict(d) for d in outcome.iterations]

        base_profile_data: dict = {
            "job_title": job_title,
            "level": level,
            "generation_mode": generation_mode,
            "candidate_facts": dict(user_profile) if user_profile else {},
            "stopped_reason": outcome.stopped_reason,
            "best_iteration_index": outcome.best_index,
            "iteration_count": len(outcome.iterations),
        }
        if user_profile is not None:
            base_profile_data["profile_fallback"] = dict(user_profile)

        generated_content: dict = {
            "content": outcome.best_content,
            "format": output_format,
            "markdown": outcome.best_content,
            "generation_mode": generation_mode,
            "placeholder_count": placeholder_count,
            "source_jd_text": jd_text,
            "candidate_facts": dict(user_profile) if user_profile else {},
            "iterations": iteration_dicts,
            "best_iteration_index": outcome.best_index,
            "stopped_reason": outcome.stopped_reason,
        }
        if outcome.best_analysis is not None:
            generated_content["best_analysis"] = outcome.best_analysis.model_dump()

        cv_entity = GeneratedCV(
            user_id=user_id,
            target_jd_text=jd_text,
            base_profile_data=base_profile_data,
            generated_content=generated_content,
            status="completed",
        )
        try:
            saved_cv = await self._cv_repo.create(cv_entity)
        except Exception as exc:
            logger.error("ImproveCV stream persist failed: %s", exc, exc_info=True)
            yield _sse("loop_error", {"error": f"Không lưu được CV: {exc}"})
            return

        # Stamp the cv_id back onto the best iteration entry for the
        # serialised payload, then emit the final event.
        for entry in generated_content["iterations"]:
            if entry["iteration_index"] == outcome.best_index:
                entry["cv_id"] = str(saved_cv.id)

        logger.info(
            "ImproveCV stream done: cv_id=%s best_idx=%d stopped=%s",
            saved_cv.id,
            outcome.best_index,
            outcome.stopped_reason,
        )

        yield _sse(
            "loop_done",
            {
                "cv_id": str(saved_cv.id),
                "best_iteration_index": outcome.best_index,
                "stopped_reason": outcome.stopped_reason,
                "overall_score": (
                    outcome.best_analysis.overall_score
                    if outcome.best_analysis
                    else None
                ),
                "verdict": (
                    outcome.best_analysis.verdict if outcome.best_analysis else None
                ),
                "iteration_count": len(outcome.iterations),
            },
        )

    @staticmethod
    def iteration_records(outcome: LoopOutcome, best_cv_id: UUID | None) -> list[IterationRecord]:
        """Build canonical :class:`IterationRecord`s from a loop outcome.

        Currently unused by ``execute`` (which serialises iterations as
        dicts for JSON storage), but exposed so future callers — Phase 3
        SSE streams or admin tooling — can get the typed shape without
        re-running the loop.
        """
        records: list[IterationRecord] = []
        for data in outcome.iterations:
            records.append(
                IterationRecord(
                    iteration_index=data.iteration_index,
                    cv_id=best_cv_id if data.iteration_index == outcome.best_index else None,
                    overall_score=data.overall_score,
                    verdict=data.verdict,
                    gap_analysis=data.gap_analysis,
                    latency_ms=data.latency_ms,
                    tokens_used=None,
                )
            )
        return records
