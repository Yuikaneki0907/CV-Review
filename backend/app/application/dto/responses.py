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
    phone_number: Optional[str] = None

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
    jd_evaluation: Optional[Dict] = None
    interview_questions: Optional[List[Dict]] = None
    salary_negotiation: Optional[Dict] = None

    model_config = {"from_attributes": True}


class AnalysisListResponse(BaseModel):
    id: UUID
    status: str
    cv_filename: str
    overall_score: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GeneratedCVListResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    version: int
    status: str
    target_jd_text: Optional[str] = None
    job_title: Optional[str] = None
    level: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GeneratedCVResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    version: int
    parent_version_id: Optional[UUID] = None
    status: str
    target_jd_text: Optional[str] = None
    base_profile_data: Optional[Dict] = None
    generated_content: Dict
    created_at: datetime

    model_config = {"from_attributes": True}


class GeneratedCVVersionResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    version: int
    parent_version_id: Optional[UUID] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatContextResponse(BaseModel):
    reply: str
    generated_cv_id: Optional[UUID] = None
