"""Canonical analyzer-output schema.

Field shape matches the Phase 1 spec:

    {
      "overall_score": float,
      "verdict": "PASS" | "BORDERLINE" | "FAIL",
      "dimension_scores": {
        "relevance":           {score, reason},
        "keyword_coverage":    {score, reason},
        "achievement_quality": {score, reason},
        "structure":           {score, reason},
        "summary_alignment":   {score, reason}
      },
      "gap_analysis":   {"critical_missing": [...], "improvable": [...]},
      "keyword_report": {"found": [...], "missing": [...], "density_ok": bool},
      "suggestions":    [{"section", "issue", "current", "suggested"}],
      "analysis_meta":  {...}
    }

Verdict thresholds (canonical, used by ``aggregator.derive_verdict``):
    PASS       overall_score >= 70
    BORDERLINE 50 <= overall_score < 70
    FAIL       overall_score < 50
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["PASS", "BORDERLINE", "FAIL"]
DimensionName = Literal[
    "relevance",
    "keyword_coverage",
    "achievement_quality",
    "structure",
    "summary_alignment",
]

# Canonical weights, summing to 1.0. The aggregator imports these so the
# scorer modules don't have to know about each other.
DIMENSION_WEIGHTS: dict[DimensionName, float] = {
    "relevance": 0.30,
    "keyword_coverage": 0.25,
    "achievement_quality": 0.20,
    "structure": 0.15,
    "summary_alignment": 0.10,
}

PASS_THRESHOLD: float = 70.0
BORDERLINE_THRESHOLD: float = 50.0


class DimensionScore(BaseModel):
    """One scoring dimension's score plus a short reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: float  # 0..100; clamped by the aggregator
    reason: str = ""


class DimensionScores(BaseModel):
    """All five dimensions in canonical order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relevance: DimensionScore
    keyword_coverage: DimensionScore
    achievement_quality: DimensionScore
    structure: DimensionScore
    summary_alignment: DimensionScore

    def as_pairs(self) -> list[tuple[DimensionName, DimensionScore]]:
        """Iterate dimensions in canonical order."""
        return [
            ("relevance", self.relevance),
            ("keyword_coverage", self.keyword_coverage),
            ("achievement_quality", self.achievement_quality),
            ("structure", self.structure),
            ("summary_alignment", self.summary_alignment),
        ]


class KeywordReport(BaseModel):
    """JD-vs-CV keyword coverage.

    Attributes:
        found: JD keywords that appear in the CV (normalised).
        missing: JD keywords absent from the CV (normalised).
        density_ok: True when keyword density is healthy — found/total
            ≥ 0.5 for must-have keywords. False means the CV mentions
            keywords too sparsely to clear ATS-style filters.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    found: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    density_ok: bool = True


class GapAnalysis(BaseModel):
    """Two prioritised buckets of gaps.

    Attributes:
        critical_missing: Hard requirements the CV fails to address
            (e.g. missing must-have keywords, missing entire sections,
            template-only output).
        improvable: Soft issues the CV could fix to score higher
            (e.g. low achievement quality, weak summary alignment).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    critical_missing: list[str] = Field(default_factory=list)
    improvable: list[str] = Field(default_factory=list)


class Suggestion(BaseModel):
    """A concrete rewrite proposal.

    Attributes:
        section: Which CV section the issue is in (e.g. "Summary",
            "Experience: Acme Engineer", "Skills").
        issue: Short label for the problem (e.g.
            "missing must-have keyword", "no quantifiable impact").
        current: The CV text as-is (1-2 sentences max).
        suggested: A rewrite the candidate could paste in.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    section: str
    issue: str
    current: str
    suggested: str


class AnalysisResultSchema(BaseModel):
    """The full analyzer output.

    Attributes:
        overall_score: Weighted sum of dimension scores, 0..100.
        verdict: Bucket assigned by :data:`PASS_THRESHOLD` /
            :data:`BORDERLINE_THRESHOLD`.
        dimension_scores: Per-dimension breakdown.
        gap_analysis: ``critical_missing`` / ``improvable`` buckets used
            by Phase 3 to drive revisions.
        keyword_report: Matched / missing JD keywords.
        suggestions: Concrete rewrite proposals (only populated when
            ``verdict != "PASS"``).
        analysis_meta: Provenance and debugging — e.g.
            ``{"source": "generated_cv", "short_circuit": "template_only_cv"}``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_score: float
    verdict: Verdict
    dimension_scores: DimensionScores
    gap_analysis: GapAnalysis
    keyword_report: KeywordReport
    suggestions: list[Suggestion] = Field(default_factory=list)
    analysis_meta: dict = Field(default_factory=dict)
