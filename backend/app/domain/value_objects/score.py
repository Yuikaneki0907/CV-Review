from dataclasses import dataclass


@dataclass(frozen=True)
class MatchScore:
    """Overall match score between CV and JD."""

    overall: float  # 0.0 - 100.0
    skills_score: float  # 0.0 - 100.0
    experience_score: float  # 0.0 - 100.0
    tools_score: float  # 0.0 - 100.0

    def __post_init__(self) -> None:
        for field_name in ["overall", "skills_score", "experience_score", "tools_score"]:
            value = getattr(self, field_name)
            if not (0.0 <= value <= 100.0):
                raise ValueError(f"{field_name} must be between 0 and 100, got {value}")
