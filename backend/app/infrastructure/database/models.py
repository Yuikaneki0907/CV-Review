import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
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
    phone_number = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    analyses = relationship("AnalysisModel", back_populates="user", lazy="selectin")
    password_reset_tokens = relationship(
        "PasswordResetTokenModel",
        back_populates="user",
        lazy="selectin",
    )


class PasswordResetTokenModel(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserModel", back_populates="password_reset_tokens")


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

    # Advanced Insights
    jd_evaluation = Column(JSONB, nullable=True)
    interview_questions = Column(JSONB, nullable=True)
    salary_negotiation = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    user = relationship("UserModel", back_populates="analyses")


class CVFileModel(Base):
    __tablename__ = "cv_files"
    __table_args__ = (
        Index(
            "ux_cv_files_user_filename_version_active",
            "user_id",
            "original_filename",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=True, index=True)

    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(512), nullable=False, unique=True)
    content_type = Column(String(100), default="application/octet-stream")
    file_size = Column(Integer, default=0)
    version = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    user = relationship("UserModel")
    analysis = relationship("AnalysisModel")


class GeneratedCVModel(Base):
    __tablename__ = "generated_cvs"
    __table_args__ = (
        Index(
            "ux_generated_cvs_user_conversation_version_active",
            "user_id",
            "conversation_id",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=False, index=True, default=uuid.uuid4)
    version = Column(Integer, nullable=False, default=1)
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("generated_cvs.id"), nullable=True)

    target_jd_text = Column(Text, nullable=True)
    base_profile_data = Column(JSONB, nullable=True)

    generated_content = Column(JSONB, nullable=False)
    status = Column(String(20), default="draft")

    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    user = relationship("UserModel")
