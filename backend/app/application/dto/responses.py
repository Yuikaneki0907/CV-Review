from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str

    model_config = {"from_attributes": True}


class SkillResponse(BaseModel):
    name: str
    category: str = ""
    proficiency: str = ""


class ScoreResponse(BaseModel):
    overall: float
    skills_score: float
    experience_score: float
    tools_score: float


class DiffSegmentResponse(BaseModel):
    text: str
    diff_type: str  # "unchanged", "added", "removed"


class HallucinationWarningResponse(BaseModel):
    section: str
    original_text: str
    rewritten_text: str
    issue_type: str
    explanation: str
    level: str


class AnalysisResponse(BaseModel):
    id: UUID
    status: str
    cv_filename: str
    jd_text: str = ""
    created_at: datetime
    completed_at: Optional[datetime] = None

    # Results (null until completed)
    cv_extracted: Optional[Dict] = None
    jd_extracted: Optional[Dict] = None
    score: Optional[ScoreResponse] = None
    matched_skills: Optional[List[SkillResponse]] = None
    missing_skills: Optional[List[SkillResponse]] = None
    extra_skills: Optional[List[SkillResponse]] = None
    rewritten_cv: Optional[str] = None
    diff_segments: Optional[List[DiffSegmentResponse]] = None
    hallucination_warnings: Optional[List[HallucinationWarningResponse]] = None

    model_config = {"from_attributes": True}


class AnalysisListResponse(BaseModel):
    id: UUID
    status: str
    cv_filename: str
    overall_score: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}
