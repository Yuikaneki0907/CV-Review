from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.analysis_result import AnalysisResult
from app.domain.entities.cv import AnalysisStatus
from app.domain.value_objects.score import MatchScore
from app.domain.value_objects.skill import Skill, SkillAnalysis
from app.domain.value_objects.diff_segment import DiffSegment, DiffResult, DiffType
from app.domain.value_objects.hallucination import (
    HallucinationWarning,
    HallucinationReport,
    WarningLevel,
)
from app.application.interfaces.repositories import IAnalysisRepository
from app.infrastructure.database.models import AnalysisModel


class AnalysisRepository(IAnalysisRepository):
    """Concrete implementation of IAnalysisRepository using SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, analysis: AnalysisResult) -> AnalysisResult:
        db_model = AnalysisModel(
            id=analysis.id,
            user_id=analysis.user_id,
            status=analysis.status.value,
            cv_filename=analysis.cv_filename,
            cv_text=analysis.cv_text,
            jd_text=analysis.jd_text,
        )
        self._session.add(db_model)
        await self._session.flush()
        return analysis

    async def get_by_id(self, analysis_id: UUID) -> Optional[AnalysisResult]:
        result = await self._session.execute(
            select(AnalysisModel).where(AnalysisModel.id == analysis_id)
        )
        db_model = result.scalar_one_or_none()
        return self._to_entity(db_model) if db_model else None

    async def update(self, analysis: AnalysisResult) -> AnalysisResult:
        result = await self._session.execute(
            select(AnalysisModel).where(AnalysisModel.id == analysis.id)
        )
        db_model = result.scalar_one_or_none()
        if not db_model:
            raise ValueError(f"Analysis {analysis.id} not found")

        db_model.status = analysis.status.value
        db_model.cv_text = analysis.cv_text
        db_model.jd_text = analysis.jd_text
        db_model.cv_extracted = analysis.cv_extracted
        db_model.jd_extracted = analysis.jd_extracted

        if analysis.score:
            db_model.overall_score = analysis.score.overall
            db_model.skills_score = analysis.score.skills_score
            db_model.experience_score = analysis.score.experience_score
            db_model.tools_score = analysis.score.tools_score

        if analysis.skill_analysis:
            db_model.matched_skills = [
                {"name": s.name, "category": s.category} for s in analysis.skill_analysis.matched_skills
            ]
            db_model.missing_skills = [
                {"name": s.name, "category": s.category} for s in analysis.skill_analysis.missing_skills
            ]
            db_model.extra_skills = [
                {"name": s.name, "category": s.category} for s in analysis.skill_analysis.extra_skills
            ]

        db_model.rewritten_cv = analysis.rewritten_cv

        if analysis.diff_result:
            db_model.diff_data = [
                {"text": seg.text, "diff_type": seg.diff_type.value}
                for seg in analysis.diff_result.segments
            ]

        if analysis.hallucination_report:
            db_model.hallucination_warnings = [
                {
                    "section": w.section,
                    "original_text": w.original_text,
                    "rewritten_text": w.rewritten_text,
                    "issue_type": w.issue_type,
                    "explanation": w.explanation,
                    "level": w.level.value,
                }
                for w in analysis.hallucination_report.warnings
            ]

        db_model.completed_at = analysis.completed_at
        await self._session.flush()
        return analysis

    async def get_by_user_id(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> List[AnalysisResult]:
        result = await self._session.execute(
            select(AnalysisModel)
            .where(AnalysisModel.user_id == user_id)
            .order_by(AnalysisModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_stuck_analyses(self) -> List[AnalysisResult]:
        """Return all analyses stuck in PENDING or PROCESSING status."""
        result = await self._session.execute(
            select(AnalysisModel).where(
                AnalysisModel.status.in_([
                    AnalysisStatus.PENDING.value,
                    AnalysisStatus.PROCESSING.value,
                ])
            )
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(model: AnalysisModel) -> AnalysisResult:
        score = None
        if model.overall_score is not None:
            score = MatchScore(
                overall=model.overall_score,
                skills_score=model.skills_score or 0,
                experience_score=model.experience_score or 0,
                tools_score=model.tools_score or 0,
            )

        skill_analysis = None
        if model.matched_skills is not None:
            skill_analysis = SkillAnalysis(
                matched_skills=[Skill(name=s["name"], category=s.get("category", "")) for s in (model.matched_skills or [])],
                missing_skills=[Skill(name=s["name"], category=s.get("category", "")) for s in (model.missing_skills or [])],
                extra_skills=[Skill(name=s["name"], category=s.get("category", "")) for s in (model.extra_skills or [])],
            )

        diff_result = None
        if model.diff_data:
            diff_result = DiffResult(
                segments=[
                    DiffSegment(text=d["text"], diff_type=DiffType(d["diff_type"]))
                    for d in model.diff_data
                ]
            )

        hallucination_report = None
        if model.hallucination_warnings is not None:
            warnings = [
                HallucinationWarning(
                    section=w["section"],
                    original_text=w["original_text"],
                    rewritten_text=w["rewritten_text"],
                    issue_type=w["issue_type"],
                    explanation=w["explanation"],
                    level=WarningLevel(w.get("level", "medium")),
                )
                for w in model.hallucination_warnings
            ]
            hallucination_report = HallucinationReport(
                warnings=warnings,
                is_safe=not any(w.level == WarningLevel.HIGH for w in warnings),
            )

        return AnalysisResult(
            id=model.id,
            user_id=model.user_id,
            status=AnalysisStatus(model.status),
            cv_filename=model.cv_filename,
            cv_text=model.cv_text,
            jd_text=model.jd_text,
            cv_extracted=model.cv_extracted,
            jd_extracted=model.jd_extracted,
            score=score,
            skill_analysis=skill_analysis,
            rewritten_cv=model.rewritten_cv,
            diff_result=diff_result,
            hallucination_report=hallucination_report,
            created_at=model.created_at,
            completed_at=model.completed_at,
        )
