"""Normalize an imported CV's markdown via the LLM.

The import pipeline (``infrastructure.file_parsers.import_pipeline``) is
deterministic and lossy on multi-column / iconified PDFs. After the user
opts in, this service asks the LLM to re-group / re-indent the parsed
markdown into a clean structure, under strict no-content-change rules
(see ``prompts/cv_normalize.txt``).

The service NEVER rewrites or adds content — if the LLM violates the
rules and drops > ``CONTENT_LOSS_TOLERANCE`` of the alphanumeric input
tokens, the call is rejected and the original content is returned with
a warning. This keeps the user safe from silent paraphrasing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.application.interfaces.ai_service import IAIService
from app.application.prompts import render_prompt
from app.logger import get_logger

logger = get_logger("app.application.services.generation.normalize_import")

_MIN_NORMALIZED_CHARS = 80
# Allow some shrinkage (page-number / repeated-header noise removal) but
# anything dropping more than this fraction of the original token set is
# treated as content loss → reject.
CONTENT_LOSS_TOLERANCE = 0.15
_TOKEN_PATTERN = re.compile(r"[A-Za-zÀ-ỹ0-9]{2,}")


@dataclass(frozen=True)
class NormalizeOutput:
    """Result of one normalize-import call.

    Attributes:
        content: Returned markdown (always non-empty — falls back to
            input on any failure).
        changed: True when the LLM produced a usable, content-preserving
            rewrite. False when the call was skipped or rejected.
        warnings: Diagnostic codes — ``"ai_provider_failed"``,
            ``"ai_returned_empty"``, ``"cv_too_short"``,
            ``"content_loss_detected"``, ``"input_empty"``.
    """

    content: str
    changed: bool
    warnings: list[str] = field(default_factory=list)


def _token_set(text: str) -> set[str]:
    """Lowercased multi-char alphanumeric tokens — used for the
    content-preservation check. Two-char threshold filters out stray
    single letters that PDF parsing tends to inject."""
    return {match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text or "")}


def _content_loss_ratio(original: str, normalized: str) -> float:
    """Fraction of original tokens missing from the normalized output.

    Empty original → 0.0 (nothing to lose). The threshold check uses
    this against :data:`CONTENT_LOSS_TOLERANCE`.
    """
    original_tokens = _token_set(original)
    if not original_tokens:
        return 0.0
    normalized_tokens = _token_set(normalized)
    missing = original_tokens - normalized_tokens
    return len(missing) / len(original_tokens)


async def normalize_imported_cv(
    *,
    raw_cv: str,
    ai_service: IAIService,
) -> NormalizeOutput:
    """Run the strict-rewrite normalize pass on a freshly imported CV.

    Returns the original ``raw_cv`` (with ``changed=False`` and an
    appropriate warning) when the call fails or the result fails the
    content-preservation check. The caller is therefore safe to always
    persist ``output.content`` without an additional guard.
    """
    raw = (raw_cv or "").strip()
    if not raw:
        return NormalizeOutput(content="", changed=False, warnings=["input_empty"])

    warnings: list[str] = []
    prompt = render_prompt("cv_normalize", raw_cv=raw)

    try:
        response = await ai_service.generate_text(prompt)
    except Exception as exc:
        logger.warning("normalize_imported_cv: provider error: %s", exc, exc_info=True)
        return NormalizeOutput(content=raw, changed=False, warnings=["ai_provider_failed"])

    normalized = (response or "").strip()
    if normalized.startswith("```"):
        normalized = re.sub(r"^```[a-zA-Z]*\n?", "", normalized)
        if normalized.endswith("```"):
            normalized = normalized[:-3]
        normalized = normalized.strip()

    if not normalized:
        return NormalizeOutput(content=raw, changed=False, warnings=["ai_returned_empty"])
    if len(normalized) < _MIN_NORMALIZED_CHARS:
        warnings.append("cv_too_short")
        return NormalizeOutput(content=raw, changed=False, warnings=warnings)

    loss = _content_loss_ratio(raw, normalized)
    logger.info(
        "normalize_imported_cv: input_len=%d output_len=%d token_loss=%.3f",
        len(raw),
        len(normalized),
        loss,
    )
    if loss > CONTENT_LOSS_TOLERANCE:
        warnings.append("content_loss_detected")
        logger.warning(
            "normalize_imported_cv: rejected output, %.1f%% of input tokens missing",
            loss * 100,
        )
        return NormalizeOutput(content=raw, changed=False, warnings=warnings)

    return NormalizeOutput(content=normalized, changed=True, warnings=warnings)


__all__ = ["CONTENT_LOSS_TOLERANCE", "NormalizeOutput", "normalize_imported_cv"]
