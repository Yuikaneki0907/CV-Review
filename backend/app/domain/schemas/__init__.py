"""Pydantic schemas — the canonical wire format between modules.

These are the single source of truth for JD/CV/Analysis shapes.
Phase 1's analyzer and Phase 2's generator both bind to these schemas;
adding/renaming a field here is a contract change.
"""

from app.domain.schemas.analysis_schema import (
    AnalysisResultSchema,
    BORDERLINE_THRESHOLD,
    DIMENSION_WEIGHTS,
    DimensionName,
    DimensionScore,
    DimensionScores,
    GapAnalysis,
    KeywordReport,
    PASS_THRESHOLD,
    Suggestion,
    Verdict,
)
from app.domain.schemas.cv_schema import (
    PLACEHOLDER_PATTERN,
    CVBullet,
    CVExperienceEntry,
    CVSchema,
)
from app.domain.schemas.document_schema import ExtractedDocument
from app.domain.schemas.iteration_schema import (
    GenerationRunResult,
    IterationRecord,
    StoppedReason,
)
from app.domain.schemas.jd_schema import JDSchema, Seniority

__all__ = [
    "AnalysisResultSchema",
    "BORDERLINE_THRESHOLD",
    "CVBullet",
    "CVExperienceEntry",
    "CVSchema",
    "DIMENSION_WEIGHTS",
    "DimensionName",
    "DimensionScore",
    "DimensionScores",
    "ExtractedDocument",
    "GapAnalysis",
    "GenerationRunResult",
    "IterationRecord",
    "JDSchema",
    "KeywordReport",
    "PASS_THRESHOLD",
    "PLACEHOLDER_PATTERN",
    "Seniority",
    "StoppedReason",
    "Suggestion",
    "Verdict",
]
