"""Canonical Job Description schema.

Every JD anywhere in the system flows through this shape. The generator
must inject ``must_have_keywords`` verbatim; the scorer measures coverage
against the same field. There is no other JD representation that should
cross a module boundary.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Seniority = Literal[
    "intern",
    "fresher",
    "junior",
    "mid",
    "senior",
    "lead",
    "manager",
    "unknown",
]


class JDSchema(BaseModel):
    """Structured Job Description.

    Attributes:
        raw_text: Original JD text as supplied by the user.
        job_title: Role title (best-effort extraction).
        seniority: Normalised seniority bucket.
        must_have_keywords: Required skills/tech, lower-cased + alias-normalised.
        nice_to_have_keywords: Optional/preferred skills, normalised.
        tools: Tools/platforms mentioned (Docker, AWS, Figma, …) — normalised.
        responsibilities: Each bullet/sentence of role responsibilities.
        years_of_experience: Required YOE if explicitly stated, else None.
        domain: Industry/domain hint (fintech, ecommerce, …), else None.
        extraction_warnings: Why a downstream stage might want to short-circuit
            (e.g. "jd_too_short", "no_required_skills_found").
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_text: str
    job_title: str = ""
    seniority: Seniority = "unknown"
    must_have_keywords: list[str] = Field(default_factory=list)
    nice_to_have_keywords: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    years_of_experience: int | None = None
    domain: str | None = None
    extraction_warnings: list[str] = Field(default_factory=list)

    @classmethod
    def empty(cls, reason: str, *, raw_text: str = "") -> "JDSchema":
        """Return a sentinel JD that downstream code can detect cheaply.

        Used when extraction fails or when the JD is unusable
        (too short, garbled PDF, etc.) so callers don't need null-guards.
        """
        return cls(raw_text=raw_text, extraction_warnings=[reason])

    @property
    def is_usable(self) -> bool:
        """True if the JD has at least one must-have keyword to score against."""
        return bool(self.must_have_keywords)
