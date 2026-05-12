"""Quality gate — ensure a freshly-generated CV passes the analyzer.

Glue used by the chat-gen flow: after the LLM emits a CV markdown, we
re-analyze it against the JD that drove the generation. If
``overall_score < pass_threshold`` we run a bounded number of revise →
re-analyze cycles using the existing Phase 3 reviser, returning the
highest-scoring iteration.

Caller is responsible for skipping the gate when the JD is missing /
short — :func:`ensure_quality` still tolerates that by returning the
original CV with ``passed_gate=False`` and a warning, but burning LLM
calls when there is no JD signal is wasteful.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.interfaces.ai_service import IAIService
from app.application.services.generation.cv_reviser import revise_cv
from app.application.services.scoring import score_cv
from app.application.services.shared import extract_cv, extract_jd
from app.logger import get_logger

logger = get_logger("app.application.services.generation.quality_gate")

# TC2 in 4.1.5 requires overall_score >= 80 for system-generated CVs.
DEFAULT_PASS_THRESHOLD = 80.0
DEFAULT_MAX_REVISIONS = 1


@dataclass(frozen=True)
class QualityGateResult:
    """Outcome of one quality-gate pass.

    Attributes:
        content: Best CV markdown — either the input (gate passed
            without changes / was skipped) or a revised version.
        initial_score: Score before any revision, or 0.0 if the gate
            short-circuited.
        final_score: Score of the returned content; 0.0 on short-circuit.
        revisions_used: How many revise calls were made (0 means the
            CV passed on first analyze, or the gate was skipped).
        passed_gate: True when ``final_score >= pass_threshold``.
        warnings: Soft-failure reasons (``"jd_unusable"``,
            ``"cv_template_only"``, ``"revise_failed"``).
    """

    content: str
    initial_score: float
    final_score: float
    revisions_used: int
    passed_gate: bool
    warnings: list[str] = field(default_factory=list)


async def ensure_quality(
    *,
    cv_content: str,
    jd_text: str,
    ai_service: IAIService,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    max_revisions: int = DEFAULT_MAX_REVISIONS,
    job_title: str | None = None,
    level: str = "",
    output_format: str = "markdown",
) -> QualityGateResult:
    """Run the analyze → (revise if needed) loop on a single CV.

    Args:
        cv_content: Markdown body emitted by the LLM in the chat flow.
        jd_text: Raw JD body extracted from the chat history (or stored
            ``target_jd_text``). Caller should pre-filter on length.
        ai_service: Concrete :class:`IAIService` implementation.
        pass_threshold: Score above which the gate passes immediately.
            Defaults to 80 to match TC2.
        max_revisions: Hard cap on revise → re-analyze cycles. Default 1
            (so the latency budget stays predictable; chat UX matters).
        job_title / level: Optional context forwarded to the reviser.
        output_format: ``"markdown"`` or ``"docx"`` — echoed into the
            revise prompt.

    Returns:
        :class:`QualityGateResult`. The returned ``content`` is always
        safe to persist — never empty, never less informative than the
        input.
    """
    warnings: list[str] = []

    jd = await extract_jd(jd_text, ai_service)
    if not jd.is_usable:
        return QualityGateResult(
            content=cv_content,
            initial_score=0.0,
            final_score=0.0,
            revisions_used=0,
            passed_gate=False,
            warnings=["jd_unusable"],
        )

    cv_schema = await extract_cv(cv_content, ai_service)
    if cv_schema.is_template_only:
        return QualityGateResult(
            content=cv_content,
            initial_score=0.0,
            final_score=0.0,
            revisions_used=0,
            passed_gate=False,
            warnings=["cv_template_only"],
        )

    # Suggestions are expensive and not needed for gating — turn them off
    # for the initial analyze and every intermediate analyze. The chat
    # consumer reads the persisted CV, not the analysis payload.
    initial = await score_cv(
        cv_schema, jd, ai_service,
        analysis_meta={"source": "quality_gate", "stage": "initial"},
        enable_suggestions=False,
    )

    if initial.overall_score >= pass_threshold:
        logger.info(
            "quality_gate PASS on first analyze: score=%.1f threshold=%.1f",
            initial.overall_score, pass_threshold,
        )
        return QualityGateResult(
            content=cv_content,
            initial_score=initial.overall_score,
            final_score=initial.overall_score,
            revisions_used=0,
            passed_gate=True,
        )

    logger.info(
        "quality_gate BELOW threshold (score=%.1f < %.1f) — running up to %d revision(s)",
        initial.overall_score, pass_threshold, max_revisions,
    )

    current_cv = cv_content
    current_analysis = initial
    best_content = cv_content
    best_score = initial.overall_score
    revisions = 0

    for _ in range(max(0, max_revisions)):
        rev = await revise_cv(
            current_cv=current_cv,
            gap=current_analysis.gap_analysis,
            jd=jd,
            ai_service=ai_service,
            job_title=job_title or jd.job_title,
            level=level,
            missing_keywords=list(current_analysis.keyword_report.missing),
            output_format=output_format,
        )
        revisions += 1
        if not rev.is_valid:
            warnings.append("revise_failed")
            break

        new_schema = await extract_cv(rev.content, ai_service)
        if new_schema.is_template_only:
            warnings.append("revise_produced_template")
            break

        new_analysis = await score_cv(
            new_schema, jd, ai_service,
            analysis_meta={"source": "quality_gate", "stage": f"revision_{revisions}"},
            enable_suggestions=False,
        )

        if new_analysis.overall_score > best_score:
            best_score = new_analysis.overall_score
            best_content = rev.content

        current_cv = rev.content
        current_analysis = new_analysis

        if new_analysis.overall_score >= pass_threshold:
            break

    passed = best_score >= pass_threshold
    logger.info(
        "quality_gate done: initial=%.1f best=%.1f revisions=%d passed=%s",
        initial.overall_score, best_score, revisions, passed,
    )
    return QualityGateResult(
        content=best_content,
        initial_score=initial.overall_score,
        final_score=best_score,
        revisions_used=revisions,
        passed_gate=passed,
        warnings=warnings,
    )


__all__ = [
    "DEFAULT_MAX_REVISIONS",
    "DEFAULT_PASS_THRESHOLD",
    "QualityGateResult",
    "ensure_quality",
]
