from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from app.domain.entities.cv import AnalysisStatus
from app.domain.value_objects.score import MatchScore
from app.domain.value_objects.skill import SkillAnalysis
from app.domain.value_objects.diff_segment import DiffResult
from app.domain.value_objects.hallucination import HallucinationReport


@dataclass
class AnalysisResult:
    """Analysis result domain entity — the main aggregate."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    status: AnalysisStatus = AnalysisStatus.PENDING

    # Input
    cv_filename: str = ""
    cv_text: str = ""
    jd_text: str = ""

    # Extracted data
    cv_extracted: Optional[dict] = None
    jd_extracted: Optional[dict] = None

    # Scoring
    score: Optional[MatchScore] = None
    skill_analysis: Optional[SkillAnalysis] = None

    # Rewrite
    rewritten_cv: Optional[str] = None
    diff_result: Optional[DiffResult] = None

    # Truth-Anchoring
    hallucination_report: Optional[HallucinationReport] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def mark_processing(self) -> None:
        self.status = AnalysisStatus.PROCESSING

    def mark_completed(self) -> None:
        self.status = AnalysisStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def mark_failed(self) -> None:
        self.status = AnalysisStatus.FAILED
