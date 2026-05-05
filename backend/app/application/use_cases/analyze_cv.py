"""AnalyzeCVUseCase — five-dimension scorer.

Phase 1 rewrite. The use case is now a thin pipeline:

    extract_jd  →  extract_cv  →  score_cv  →  persist

Streaming variant (used by the SSE route) yields events between steps.

The old 6-step pipeline (rewrite_cv / check_hallucination /
visual diff / insights) has been removed. Its replacement is the
``suggestions`` field on :class:`AnalysisResultSchema` plus the
``gap_analysis`` field, both populated by
``application.services.scoring.score_cv``.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator
from uuid import UUID

from app.application.interfaces.ai_service import IAIService
from app.application.interfaces.repositories import IAnalysisRepository
from app.application.services.scoring import score_cv
from app.application.services.shared import extract_cv, extract_jd
from app.domain.entities.analysis_result import AnalysisResult
from app.domain.schemas import AnalysisResultSchema
from app.domain.value_objects.score import MatchScore
from app.domain.value_objects.skill import Skill, SkillAnalysis
from app.logger import get_logger

logger = get_logger("app.application.use_cases.analyze_cv")


# Step keys used by the SSE stream — kept stable so the frontend
# can render progress without a contract change.
STEPS = [
    {"key": "extract", "label": "Trích xuất thông tin CV & JD"},
    {"key": "score", "label": "Chấm điểm 5 chiều"},
    {"key": "done", "label": "Hoàn tất"},
]


def _attach_result_to_entity(
    analysis: AnalysisResult,
    result: AnalysisResultSchema,
) -> None:
    """Write the new schema and back-compat fields onto the entity.

    The DB schema still has fixed columns (``overall_score``,
    ``skills_score``, ``matched_skills``, …). We populate them with
    semantically-closest values so legacy frontend panels still render,
    AND we persist the canonical :class:`AnalysisResultSchema` inside
    ``analysis.analysis_meta["result"]`` for the new wire format. No
    DB migration is required.
    """
    # Canonical new representation — read by the new response DTO path.
    meta = dict(analysis.analysis_meta or {})
    meta["result"] = result.model_dump()
    meta["schema_version"] = 1
    analysis.analysis_meta = meta

    # Legacy column population (best-effort mapping):
    #   overall_score ← result.overall_score
    #   skills_score      ← keyword_coverage   (closest semantic equivalent)
    #   experience_score  ← relevance
    #   tools_score       ← achievement_quality
    analysis.score = MatchScore(
        overall=result.overall_score,
        skills_score=result.dimension_scores.keyword_coverage.score,
        experience_score=result.dimension_scores.relevance.score,
        tools_score=result.dimension_scores.achievement_quality.score,
    )

    # Skill analysis ← keyword report (legacy column).
    analysis.skill_analysis = SkillAnalysis(
        matched_skills=[Skill(name=name) for name in result.keyword_report.found],
        missing_skills=[Skill(name=name) for name in result.keyword_report.missing],
        extra_skills=[],
    )

    # Legacy "score_breakdown" — keep populated so the existing /analysis/{id}
    # response surface still has data while frontend migrates.
    analysis.score_breakdown = {
        "verdict": result.verdict,
        "dimension_scores": {
            name: {"score": dim.score, "reason": dim.reason}
            for name, dim in result.dimension_scores.as_pairs()
        },
        "gap_analysis": result.gap_analysis.model_dump(),
        "keyword_report": result.keyword_report.model_dump(),
        "suggestions": [s.model_dump() for s in result.suggestions],
    }


class AnalyzeCVUseCase:
    """Five-dimension CV analyzer.

    Backwards-compatible constructor — Celery task still passes
    ``(repo, ai_service, redis_client)``.
    """

    def __init__(
        self,
        analysis_repo: IAnalysisRepository,
        ai_service: IAIService,
        redis_client=None,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._ai_service = ai_service
        self._redis = redis_client

    # ─ Pub/Sub for SSE (unchanged from old pipeline) ─────────────
    def _publish_step(
        self,
        analysis_id: UUID,
        step_key: str,
        status: str,
        duration_ms: float = 0,
    ) -> None:
        if not self._redis:
            return
        channel = f"analysis:{analysis_id}"
        message = json.dumps(
            {"step": step_key, "status": status, "duration_ms": round(duration_ms)}
        )
        try:
            self._redis.publish(channel, message)
        except Exception as exc:
            logger.warning("Failed to publish step event: %s", exc)

    # ─ Pipeline ──────────────────────────────────────────────────
    async def _run_pipeline(self, analysis: AnalysisResult) -> AnalysisResultSchema:
        """Run extract → score, returning the schema. Used by both
        ``execute`` and ``execute_stream``.
        """
        # Concurrent extraction — JD and CV don't depend on each other.
        jd_task = extract_jd(analysis.jd_text, self._ai_service)
        cv_task = extract_cv(analysis.cv_text, self._ai_service)
        jd, cv = await asyncio.gather(jd_task, cv_task)

        # Surface the structured extracts onto the entity (legacy fields).
        analysis.jd_extracted = {
            "must_have_keywords": jd.must_have_keywords,
            "nice_to_have_keywords": jd.nice_to_have_keywords,
            "tools": jd.tools,
            "responsibilities": jd.responsibilities,
            "job_title": jd.job_title,
            "seniority": jd.seniority,
        }
        analysis.cv_extracted = {
            "skills": cv.skills,
            "tools": cv.tools,
            "summary": cv.summary,
            "placeholders_remaining": cv.placeholders_remaining,
            "candidate_facts_present": cv.candidate_facts_present,
            "experience_count": len(cv.experience),
        }

        result = await score_cv(
            cv,
            jd,
            self._ai_service,
            analysis_meta=analysis.analysis_meta,
        )
        return result

    async def execute(self, analysis_id: UUID) -> AnalysisResult:
        """Run the full pipeline for an existing analysis row.

        Args:
            analysis_id: Row id loaded by the Celery task.

        Returns:
            The persisted :class:`AnalysisResult` with the new schema
            attached.
        """
        pipeline_start = time.perf_counter()
        logger.info("Analyze pipeline START: analysis_id=%s", analysis_id)

        analysis = await self._analysis_repo.get_by_id(analysis_id)
        if not analysis:
            logger.error("Pipeline ABORT: analysis_id=%s not found", analysis_id)
            raise ValueError(f"Analysis {analysis_id} not found")

        analysis.mark_processing()
        await self._analysis_repo.update(analysis)

        try:
            self._publish_step(analysis_id, "extract", "running")
            step_start = time.perf_counter()
            result = await self._run_pipeline(analysis)
            extract_ms = (time.perf_counter() - step_start) * 1000
            self._publish_step(analysis_id, "extract", "done", extract_ms)
            self._publish_step(analysis_id, "score", "done", 0)

            _attach_result_to_entity(analysis, result)
            analysis.mark_completed()
            await self._analysis_repo.update(analysis)

            total_ms = (time.perf_counter() - pipeline_start) * 1000
            self._publish_step(analysis_id, "done", "done", total_ms)
            logger.info(
                "Analyze pipeline COMPLETE: analysis_id=%s total=%.0fms verdict=%s overall=%.1f",
                analysis_id,
                total_ms,
                result.verdict,
                result.overall_score,
            )
        except Exception:
            analysis.mark_failed()
            await self._analysis_repo.update(analysis)
            self._publish_step(
                analysis_id,
                "pipeline",
                "failed",
                (time.perf_counter() - pipeline_start) * 1000,
            )
            logger.error("Pipeline FAILED: analysis_id=%s", analysis_id, exc_info=True)
            raise

        return analysis

    # ─ Streaming variant — used by /analysis/chat-analyze/stream ─
    async def execute_stream(self, analysis_id: UUID) -> AsyncIterator[str]:
        """Yield SSE-formatted events as the pipeline runs.

        Each yielded value is a ``"event: <name>\\ndata: <json>\\n\\n"``
        string ready to write to a StreamingResponse.
        """
        def _sse(event: str, data: object) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        analysis = await self._analysis_repo.get_by_id(analysis_id)
        if not analysis:
            yield _sse("analysis_error", {"error": f"analysis {analysis_id} not found"})
            return

        yield _sse(
            "analysis_start",
            {"analysis_id": str(analysis_id), "cv_filename": analysis.cv_filename},
        )

        analysis.mark_processing()
        await self._analysis_repo.update(analysis)

        try:
            yield _sse(
                "analysis_step",
                {"step": "extract", "status": "running", "label": STEPS[0]["label"]},
            )
            t0 = time.perf_counter()
            result = await self._run_pipeline(analysis)
            t1 = time.perf_counter()
            yield _sse(
                "analysis_step",
                {"step": "extract", "status": "done", "duration_ms": round((t1 - t0) * 1000)},
            )
            yield _sse(
                "analysis_step",
                {"step": "score", "status": "done", "duration_ms": 0},
            )

            yield _sse(
                "analysis_result",
                {
                    "type": "scores",
                    "data": {
                        "overall_score": result.overall_score,
                        "verdict": result.verdict,
                        "dimension_scores": {
                            name: {"score": dim.score, "reason": dim.reason}
                            for name, dim in result.dimension_scores.as_pairs()
                        },
                    },
                },
            )
            yield _sse(
                "analysis_result",
                {
                    "type": "keyword_report",
                    "data": result.keyword_report.model_dump(),
                },
            )
            yield _sse(
                "analysis_result",
                {
                    "type": "gap_analysis",
                    "data": result.gap_analysis.model_dump(),
                },
            )
            if result.suggestions:
                yield _sse(
                    "analysis_result",
                    {
                        "type": "suggestions",
                        "data": [s.model_dump() for s in result.suggestions],
                    },
                )

            _attach_result_to_entity(analysis, result)
            analysis.mark_completed()
            await self._analysis_repo.update(analysis)

            yield _sse("analysis_done", {"analysis_id": str(analysis_id)})
        except Exception as exc:
            logger.error("Stream pipeline FAILED: analysis_id=%s", analysis_id, exc_info=True)
            analysis.mark_failed()
            await self._analysis_repo.update(analysis)
            yield _sse("analysis_error", {"error": str(exc)})
