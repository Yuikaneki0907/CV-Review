from dataclasses import dataclass, field
from enum import Enum
from typing import List


class DiffType(str, Enum):
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"


@dataclass(frozen=True)
class DiffSegment:
    """A single segment in the diff output."""

    text: str
    diff_type: DiffType


@dataclass
class DiffResult:
    """Full diff between original CV and rewritten CV."""

    segments: List[DiffSegment] = field(default_factory=list)
