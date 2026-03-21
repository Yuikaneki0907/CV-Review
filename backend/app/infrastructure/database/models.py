import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    analyses = relationship("AnalysisModel", back_populates="user", lazy="selectin")


class AnalysisModel(Base):
    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)

    # Input
    cv_filename = Column(String(255), default="")
    cv_text = Column(Text, default="")
    jd_text = Column(Text, default="")

    # Extracted data (JSONB)
    cv_extracted = Column(JSONB, nullable=True)
    jd_extracted = Column(JSONB, nullable=True)

    # Scoring
    overall_score = Column(Float, nullable=True)
    skills_score = Column(Float, nullable=True)
    experience_score = Column(Float, nullable=True)
    tools_score = Column(Float, nullable=True)
    matched_skills = Column(JSONB, nullable=True)
    missing_skills = Column(JSONB, nullable=True)
    extra_skills = Column(JSONB, nullable=True)

    # Rewrite
    rewritten_cv = Column(Text, nullable=True)
    diff_data = Column(JSONB, nullable=True)

    # Truth-Anchoring
    hallucination_warnings = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("UserModel", back_populates="analyses")


class CVFileModel(Base):
    __tablename__ = "cv_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=True, index=True)

    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(512), nullable=False, unique=True)
    content_type = Column(String(100), default="application/octet-stream")
    file_size = Column(Float, default=0)
    version = Column(Float, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserModel")
    analysis = relationship("AnalysisModel")

