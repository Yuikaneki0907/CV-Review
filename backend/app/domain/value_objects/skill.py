from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Skill:
    """A single skill extracted from CV or JD."""

    name: str
    category: str = ""  # e.g., "programming", "framework", "soft_skill"
    proficiency: str = ""  # e.g., "beginner", "intermediate", "advanced"


@dataclass
class SkillAnalysis:
    """Result of comparing CV skills vs JD requirements."""

    matched_skills: List[Skill] = field(default_factory=list)
    missing_skills: List[Skill] = field(default_factory=list)
    extra_skills: List[Skill] = field(default_factory=list)  # CV has but JD doesn't need
