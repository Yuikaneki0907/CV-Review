"""Phase 3 feedback-loop output schemas.

Defined here in Phase 0 so the Phase 1 analyzer and Phase 2 generator can
import these types when they expose hooks for the loop, without
triggering circular imports later.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.schemas.analysis_schema import AnalysisResultSchema, GapAnalysis

StoppedReason = Literal[
    "passed_threshold",
    "max_iterations",
    "no_improvement",
    "insufficient_jd",
    "extractor_failed",
]


class IterationRecord(BaseModel):
    """One iteration of the gen → analyze → revise loop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    iteration_index: int
    cv_id: UUID | None
    overall_score: float | None
    verdict: str | None
    gap_analysis: GapAnalysis | None
    latency_ms: float
    tokens_used: int | None = None


class GenerationRunResult(BaseModel):
    """Aggregate result of an analyzer-aware generation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    best_cv_id: UUID | None
    best_analysis: AnalysisResultSchema | None
    iterations: list[IterationRecord] = Field(default_factory=list)
    stopped_reason: StoppedReason
