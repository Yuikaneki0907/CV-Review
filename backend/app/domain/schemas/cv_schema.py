"""Canonical CV schema.

Every CV crossing a module boundary uses this shape. The Phase 1 scorer
reads `skills`, `tools`, `experience.bullets`, and `summary` directly;
the Phase 2 generator emits markdown that, when re-extracted, must hit
``candidate_facts_present=True`` and ``placeholders_remaining=0`` to be
considered a "real" CV.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

# Single source of truth for placeholder detection.
# Matches "[Họ và tên]", "[Email]", "<TBD>", etc.
# Replaces the four duplicate definitions previously in:
#   generate_cv.py, chat_cv.py, analysis_routes.py, analyze_cv.py
PLACEHOLDER_PATTERN = re.compile(r"\[[^\]\n]{2,80}\]|<[^>\n]{2,80}>")


class CVBullet(BaseModel):
    """A single experience/project bullet, with achievement-quality tags.

    Attributes:
        text: The bullet text as written.
        has_action_verb: True if the bullet starts with a recognised
            action verb (Built, Led, Improved, Phát triển, Triển khai, …).
        has_metric: True if the bullet contains a quantifiable result
            (number, percentage, time, scale).
        keywords_hit: Subset of JD keywords that appear in this bullet
            (populated by the scorer, empty at extraction time).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    has_action_verb: bool = False
    has_metric: bool = False
    keywords_hit: list[str] = Field(default_factory=list)


class CVExperienceEntry(BaseModel):
    """One job/project entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: str = ""
    company: str = ""
    period: str = ""
    bullets: list[CVBullet] = Field(default_factory=list)


class CVSchema(BaseModel):
    """Structured CV / candidate profile.

    Attributes:
        raw_text: Original markdown/plaintext CV.
        placeholders_remaining: Count of ``[…]`` / ``<…>`` placeholders.
        candidate_facts_present: True if the CV has any concrete candidate
            evidence (real name/email/skills); False for blank templates.
        summary: 1–4 sentence professional summary.
        skills: Normalised skill tokens.
        tools: Normalised tool tokens.
        experience: Structured work/project history.
        education: Education entries (free-form).
        extraction_warnings: e.g. "too_many_placeholders",
            "extraction_failed".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_text: str
    placeholders_remaining: int = 0
    candidate_facts_present: bool = False
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    experience: list[CVExperienceEntry] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)

    @classmethod
    def empty(cls, reason: str, *, raw_text: str = "") -> "CVSchema":
        """Sentinel CV for extraction failures."""
        return cls(
            raw_text=raw_text,
            candidate_facts_present=False,
            extraction_warnings=[reason],
        )

    @property
    def is_template_only(self) -> bool:
        """True when the CV is effectively a placeholder shell.

        Phase 1's analyzer uses this to short-circuit scoring with a
        clear ``verdict=FAIL, reason="template_only_cv"`` instead of
        running every LLM judge and producing meaningless numbers.
        """
        return (not self.candidate_facts_present) or self.placeholders_remaining > 5
