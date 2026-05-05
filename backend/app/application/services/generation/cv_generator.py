"""CV generator — Phase 2 entry point.

Mirrors the Phase 0/1 service shape: prompt assembly lives next to the
template (``prompts/cv_generation.txt``), the AI service is treated as
a thin LLM wrapper, and post-processing (placeholder count, candidate-
fact heuristics, generation_mode) lives here so the use case is just
orchestration + persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from app.application.interfaces.ai_service import IAIService
from app.domain.schemas.cv_schema import PLACEHOLDER_PATTERN
from app.logger import get_logger

logger = get_logger("app.application.services.generation.cv_generator")

# Output-format -> short instruction injected into the prompt. Kept here
# so both providers and tests share the exact wording.
_FORMAT_GUIDES: dict[str, str] = {
    "markdown": "tuân thủ markdown chuẩn, có heading và bullet list rõ ràng.",
    "docx": "tuân thủ markdown sạch để có thể export DOCX chính xác (heading/bullet rõ ràng).",
}
_DEFAULT_FORMAT_GUIDE = "tuân thủ markdown chuẩn."

# Minimum body length we accept as a "CV". Below this we refuse to save.
_MIN_GENERATED_CV_CHARS = 80


def format_guide_for(output_format: str) -> str:
    """Return the format-specific instruction string for the prompt."""
    return _FORMAT_GUIDES.get(output_format, _DEFAULT_FORMAT_GUIDE)


def build_profile_section(user_profile: Mapping[str, object] | None) -> str:
    """Render the optional ``user_profile`` block injected into the prompt.

    Returns an empty string when no profile is supplied OR when every
    supported field (full_name / email / phone_number) is missing or
    blank. The wording is duplicated verbatim in
    ``tests/test_generate_cv_profile_fallback.py`` — keep it stable.
    """
    if not user_profile:
        return ""
    lines: list[str] = []
    full_name = str(user_profile.get("full_name") or "").strip()
    email = str(user_profile.get("email") or "").strip()
    phone_number = str(user_profile.get("phone_number") or "").strip()
    if full_name:
        lines.append(f"  - Họ và tên: {full_name}")
    if email:
        lines.append(f"  - Email: {email}")
    if phone_number:
        lines.append(f"  - Số điện thoại: {phone_number}")
    if not lines:
        return ""
    return (
        "\n        Thông tin profile người dùng (dùng làm fallback cho phần Thông tin cá nhân):\n"
        + "\n".join(lines)
        + "\n        Lưu ý: Nếu người dùng đã cung cấp thông tin cá nhân trong prompt hoặc JD, "
        "ưu tiên thông tin đó. Chỉ dùng profile trên khi input không có thông tin tương ứng. "
        "Không tự bịa thêm nếu cả input lẫn profile đều không có.\n"
    )


@dataclass(frozen=True)
class GenerationOutput:
    """Result of one CV-generation call.

    Attributes:
        content: Raw markdown returned by the AI provider (already
            stripped). May still contain placeholders.
        output_format: Echo of the format the caller requested.
        placeholders_remaining: Count of ``[…]`` / ``<…>`` markers
            still in the body.
        candidate_facts_present: True when ``user_profile`` contributed
            at least one non-empty field to the prompt.
        generation_mode: ``"personalized"`` when no placeholders remain,
            otherwise ``"template_only"``. Phase 3's feedback loop reads
            this to decide whether to short-circuit.
        warnings: Soft-failure reasons (e.g. ``"cv_too_short"``,
            ``"ai_returned_empty"``).
    """

    content: str
    output_format: str
    placeholders_remaining: int
    candidate_facts_present: bool
    generation_mode: str
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when the generated body is long enough to persist."""
        return len(self.content.strip()) >= _MIN_GENERATED_CV_CHARS and not any(
            w in {"ai_returned_empty", "cv_too_short"} for w in self.warnings
        )


def _has_profile_facts(user_profile: Mapping[str, object] | None) -> bool:
    if not user_profile:
        return False
    for key in ("full_name", "email", "phone_number"):
        if str(user_profile.get(key) or "").strip():
            return True
    return False


async def generate_cv(
    *,
    job_title: str,
    jd_text: str,
    level: str,
    ai_service: IAIService,
    output_format: str = "markdown",
    user_profile: Mapping[str, object] | None = None,
) -> GenerationOutput:
    """Run one CV generation pass.

    Args:
        job_title: Target role title from the request.
        jd_text: Raw JD body (already untrusted-stripped by the caller).
        level: Seniority string (``"Fresher"`` / ``"Junior"`` / …).
        ai_service: Concrete :class:`IAIService` implementation.
        output_format: ``"markdown"`` (default) or ``"docx"``. Controls
            the format-guide line baked into the prompt.
        user_profile: Optional candidate facts to inject as the
            ``profile_section`` fallback.

    Returns:
        :class:`GenerationOutput` describing the markdown the provider
        returned. The use case decides whether to persist based on
        :pyattr:`GenerationOutput.is_valid`.
    """
    warnings: list[str] = []

    try:
        raw = await ai_service.generate_cv_template(
            job_title=job_title,
            jd_text=jd_text,
            level=level,
            output_format=output_format,
            user_profile=dict(user_profile) if user_profile is not None else None,
        )
    except Exception as exc:
        logger.warning("generate_cv: ai_service error: %s", exc, exc_info=True)
        warnings.append("ai_provider_failed")
        raw = ""

    content = (raw or "").strip()
    if not content:
        warnings.append("ai_returned_empty")

    placeholder_count = len(PLACEHOLDER_PATTERN.findall(content))
    candidate_facts_present = _has_profile_facts(user_profile)
    generation_mode = "personalized" if placeholder_count == 0 else "template_only"

    if content and len(content) < _MIN_GENERATED_CV_CHARS:
        warnings.append("cv_too_short")

    output = GenerationOutput(
        content=content,
        output_format=output_format,
        placeholders_remaining=placeholder_count,
        candidate_facts_present=candidate_facts_present,
        generation_mode=generation_mode,
        warnings=warnings,
    )
    logger.info(
        "generate_cv: title=%r level=%s mode=%s placeholders=%d facts=%s len=%d",
        job_title,
        level,
        generation_mode,
        placeholder_count,
        candidate_facts_present,
        len(content),
    )
    return output


__all__ = [
    "GenerationOutput",
    "build_profile_section",
    "format_guide_for",
    "generate_cv",
]
