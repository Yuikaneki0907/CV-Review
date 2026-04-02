from dataclasses import dataclass, field
from enum import Enum
from typing import List


class WarningLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class HallucinationWarning:
    """A single hallucination or over-claiming warning."""

    section: str  # Which part of the rewritten CV
    original_text: str  # What the original CV said
    rewritten_text: str  # What the AI wrote
    issue_type: str  # "hallucination" or "over_claiming"
    explanation: str  # Why this is flagged
    level: WarningLevel = WarningLevel.MEDIUM


@dataclass
class HallucinationReport:
    """Full truth-anchoring report."""

    warnings: List[HallucinationWarning] = field(default_factory=list)
    is_safe: bool = True  # True if no high-level warnings

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def high_risk_count(self) -> int:
        return len([w for w in self.warnings if w.level == WarningLevel.HIGH])
