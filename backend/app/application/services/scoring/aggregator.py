"""Five-dimension aggregator — the public ``score_cv`` entrypoint.

Flow:

1. Pre-flight short-circuits — empty/usable JD, template-only CV.
2. Run the three deterministic dimensions in process.
3. Run the two LLM-judged dimensions concurrently.
4. Compute weighted overall score.
5. Derive verdict + gap analysis from dimension scores.
6. If ``verdict != PASS`` — ask the LLM for concrete suggestions.
7. Assemble :class:`AnalysisResultSchema`.

The aggregator never raises on partial failure — judge timeouts /
parse errors are absorbed into the dimension's reason field and the
overall score reflects whatever signal we did get.
"""
from __future__ import annotations

import asyncio

from app.application.interfaces.ai_service import IAIService
from app.application.services.scoring import (
    achievement_quality,
    keyword_coverage,
    relevance,
    structure,
    summary_alignment,
    suggestions,
)
from app.domain.schemas import (
    AnalysisResultSchema,
    BORDERLINE_THRESHOLD,
    CVSchema,
    DimensionName,
    DimensionScore,
    DimensionScores,
    GapAnalysis,
    JDSchema,
    KeywordReport,
    PASS_THRESHOLD,
    Suggestion,
    Verdict,
)
from app.domain.schemas.analysis_schema import DIMENSION_WEIGHTS
from app.logger import get_logger

logger = get_logger("app.application.services.scoring.aggregator")


def derive_verdict(overall_score: float) -> Verdict:
    """Map an overall score to a verdict bucket.

    Thresholds: PASS ≥ 70, BORDERLINE 50..69, FAIL < 50.
    """
    if overall_score >= PASS_THRESHOLD:
        return "PASS"
    if overall_score >= BORDERLINE_THRESHOLD:
        return "BORDERLINE"
    return "FAIL"


def compute_overall(dimension_scores: DimensionScores) -> float:
    """Compute the weighted overall score (0..100).

    Each dimension contributes ``weight * score``. All five weights sum
    to 1.0 by construction, so an all-100 input yields 100.
    """
    total = 0.0
    for name, dim in dimension_scores.as_pairs():
        weight = DIMENSION_WEIGHTS[name]
        total += weight * dim.score
    return round(max(0.0, min(100.0, total)), 1)


def _build_gap_analysis(
    dim: DimensionScores,
    keyword_report: KeywordReport,
    cv: CVSchema,
) -> GapAnalysis:
    """Derive critical_missing / improvable buckets from scores.

    Critical = anything the candidate cannot fix by rewording (missing
    must-have keywords, missing sections, template-only output).
    Improvable = scores that are below 70 in dimensions where wording
    or structure can be fixed.
    """
    critical: list[str] = []
    improvable: list[str] = []

    if keyword_report.missing:
        for kw in keyword_report.missing[:8]:
            critical.append(f"missing keyword: {kw}")

    # Structure-related critical items.
    if not cv.candidate_facts_present:
        critical.append("CV has no concrete candidate facts (template-only)")
    if cv.placeholders_remaining > 0:
        critical.append(f"{cv.placeholders_remaining} placeholders remain in the CV")
    if not cv.summary.strip():
        critical.append("CV is missing a Summary section")
    if not cv.experience:
        critical.append("CV is missing an Experience section")

    # Improvable: dimensions scoring below PASS threshold.
    threshold_for_improvable = PASS_THRESHOLD
    for name, score in dim.as_pairs():
        if score.score < threshold_for_improvable and name not in {
            "keyword_coverage",
            "structure",
        }:
            improvable.append(
                f"{name.replace('_', ' ')} below {int(threshold_for_improvable)}: {score.reason}"
            )

    # De-dupe.
    return GapAnalysis(
        critical_missing=list(dict.fromkeys(critical)),
        improvable=list(dict.fromkeys(improvable)),
    )


def _short_circuit_result(
    *,
    overall: float,
    verdict: Verdict,
    reason_code: str,
    reason_text: str,
    keyword_report: KeywordReport,
    gap: GapAnalysis,
    analysis_meta: dict | None,
) -> AnalysisResultSchema:
    """Build an ``AnalysisResultSchema`` for an early-exit case.

    Used when we know enough up front to fail fast — JD unusable,
    CV template-only — without burning LLM calls.
    """
    zero_dim = DimensionScore(score=overall, reason=reason_text)
    meta = dict(analysis_meta or {})
    meta["short_circuit"] = reason_code
    return AnalysisResultSchema(
        overall_score=overall,
        verdict=verdict,
        dimension_scores=DimensionScores(
            relevance=zero_dim,
            keyword_coverage=zero_dim,
            achievement_quality=zero_dim,
            structure=zero_dim,
            summary_alignment=zero_dim,
        ),
        gap_analysis=gap,
        keyword_report=keyword_report,
        suggestions=[],
        analysis_meta=meta,
    )


async def score_cv(
    cv: CVSchema,
    jd: JDSchema,
    ai_service: IAIService,
    *,
    analysis_meta: dict | None = None,
    enable_suggestions: bool = True,
) -> AnalysisResultSchema:
    """Score a CV against a JD across the five dimensions.

    Args:
        cv: Structured CV from ``shared.cv_extractor.extract_cv``.
        jd: Structured JD from ``shared.jd_extractor.extract_jd``.
        ai_service: AI provider for the LLM-judged dimensions.
        analysis_meta: Provenance the caller wants threaded through
            (e.g. ``{"source": "generated_cv"}``).
        enable_suggestions: If True (default), generate rewrite
            suggestions when ``verdict != PASS``. Phase 3's feedback
            loop turns this off on intermediate iterations to save
            tokens.

    Returns:
        Fully populated :class:`AnalysisResultSchema`.
    """
    # ─ Pre-flight: insufficient JD ───────────────────────────────
    if not jd.is_usable:
        keyword_report = KeywordReport(found=[], missing=[], density_ok=False)
        gap = GapAnalysis(
            critical_missing=[
                "JD could not be parsed for required skills",
                *jd.extraction_warnings,
            ],
            improvable=[],
        )
        return _short_circuit_result(
            overall=0.0,
            verdict="FAIL",
            reason_code="insufficient_jd",
            reason_text="JD has no must-have keywords to score against",
            keyword_report=keyword_report,
            gap=gap,
            analysis_meta=analysis_meta,
        )

    # ─ Pre-flight: template-only CV ──────────────────────────────
    if cv.is_template_only:
        # Still compute keyword coverage — the generator may have injected
        # keywords even in template mode, and we want to surface that.
        kw_score, kw_report = keyword_coverage.evaluate(cv, jd)
        gap = GapAnalysis(
            critical_missing=[
                "CV has no concrete candidate facts (template-only)",
                *(f"missing keyword: {kw}" for kw in kw_report.missing[:5]),
            ],
            improvable=[],
        )
        return _short_circuit_result(
            overall=0.0,
            verdict="FAIL",
            reason_code="template_only_cv",
            reason_text="CV is template-only; needs concrete candidate evidence before scoring",
            keyword_report=kw_report,
            gap=gap,
            analysis_meta=analysis_meta,
        )

    # ─ Deterministic dimensions ──────────────────────────────────
    kw_dim, kw_report = keyword_coverage.evaluate(cv, jd)
    ach_dim = achievement_quality.evaluate(cv)
    struct_dim = structure.evaluate(cv)

    # ─ LLM-judged dimensions in parallel ─────────────────────────
    relevance_task = relevance.evaluate(cv, jd, ai_service)
    summary_task = summary_alignment.evaluate(cv, jd, ai_service)
    rel_dim, sum_dim = await asyncio.gather(relevance_task, summary_task)

    dim_scores = DimensionScores(
        relevance=rel_dim,
        keyword_coverage=kw_dim,
        achievement_quality=ach_dim,
        structure=struct_dim,
        summary_alignment=sum_dim,
    )
    overall = compute_overall(dim_scores)
    verdict = derive_verdict(overall)
    gap = _build_gap_analysis(dim_scores, kw_report, cv)

    # ─ Suggestions (only when not PASS) ──────────────────────────
    suggestion_list: list[Suggestion] = []
    if enable_suggestions and verdict != "PASS":
        suggestion_list = await suggestions.generate(cv, jd, gap, ai_service)

    logger.info(
        "score_cv: overall=%.1f verdict=%s dims=(rel=%.1f kw=%.1f ach=%.1f str=%.1f sum=%.1f) "
        "suggestions=%d",
        overall,
        verdict,
        rel_dim.score,
        kw_dim.score,
        ach_dim.score,
        struct_dim.score,
        sum_dim.score,
        len(suggestion_list),
    )

    return AnalysisResultSchema(
        overall_score=overall,
        verdict=verdict,
        dimension_scores=dim_scores,
        gap_analysis=gap,
        keyword_report=kw_report,
        suggestions=suggestion_list,
        analysis_meta=dict(analysis_meta or {}),
    )
