"""Shared services consumed by both gen_cv and analyze_cv.

These are the single source of truth for:
- PDF/DOCX/text extraction (``document_extractor``)
- Skill/keyword normalisation (``skill_normalisation``)
- JD structuring (``jd_extractor``)
- CV structuring (``cv_extractor``)

If a feature module reimplements any of these, it has drifted — fix the
import, don't fork the logic.
"""

from app.application.services.shared.cv_extractor import extract_cv
from app.application.services.shared.document_extractor import extract_document_text
from app.application.services.shared.jd_extractor import extract_jd
from app.application.services.shared.skill_normalisation import (
    SKILL_ALIASES,
    normalize_skill_token,
    normalize_skill_tokens,
)

__all__ = [
    "SKILL_ALIASES",
    "extract_cv",
    "extract_document_text",
    "extract_jd",
    "normalize_skill_token",
    "normalize_skill_tokens",
]
