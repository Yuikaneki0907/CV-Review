import difflib
import json
import time
from typing import List, Optional
from uuid import UUID

import numpy as np

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
from app.application.interfaces.ai_service import IAIService
from app.logger import get_logger

logger = get_logger("app.application.analyze_cv")

# Step definitions for streaming
STEPS = [
    {"key": "extract", "label": "Trích xuất thông tin CV"},
    {"key": "score", "label": "Matching & Scoring"},
    {"key": "rewrite", "label": "Viết lại CV"},
    {"key": "truthcheck", "label": "Kiểm tra hallucination"},
    {"key": "diff", "label": "Tạo visual diff"},
]


class AnalyzeCVUseCase:
    """Main orchestrator — runs the full CV analysis pipeline."""

    def __init__(
        self,
        analysis_repo: IAnalysisRepository,
        ai_service: IAIService,
        redis_client=None,
    ):
        self._analysis_repo = analysis_repo
        self._ai_service = ai_service
        self._redis = redis_client

    def _publish_step(self, analysis_id: UUID, step_key: str, status: str, duration_ms: float = 0):
        """Publish step progress to Redis for SSE streaming."""
        if not self._redis:
            return
        channel = f"analysis:{analysis_id}"
        message = json.dumps({
            "step": step_key,
            "status": status,
            "duration_ms": round(duration_ms),
        })
        try:
            self._redis.publish(channel, message)
            logger.debug("Published to %s: %s", channel, message)
        except Exception as e:
            logger.warning("Failed to publish step event: %s", e)

    async def execute(self, analysis_id: UUID) -> AnalysisResult:
        """Run the full analysis pipeline for a given analysis record."""

        pipeline_start = time.perf_counter()
        logger.info("Pipeline START: analysis_id=%s", analysis_id)

        analysis = await self._analysis_repo.get_by_id(analysis_id)
        if not analysis:
            logger.error("Pipeline ABORT: analysis_id=%s not found", analysis_id)
            raise ValueError(f"Analysis {analysis_id} not found")

        analysis.mark_processing()
        await self._analysis_repo.update(analysis)

        try:
            # Step 1: Extract structured info from CV and JD
            self._publish_step(analysis_id, "extract", "running")
            step_start = time.perf_counter()
            cv_extracted = await self._ai_service.extract_cv_info(analysis.cv_text)
            jd_extracted = await self._ai_service.extract_jd_info(analysis.jd_text)
            analysis.cv_extracted = cv_extracted
            analysis.jd_extracted = jd_extracted
            step_ms = (time.perf_counter() - step_start) * 1000
            logger.info("Step 1 DONE (extract): %.0fms", step_ms)
            await self._analysis_repo.update(analysis)
            self._publish_step(analysis_id, "extract", "done", step_ms)

            # Step 2: Match & Score using embeddings
            self._publish_step(analysis_id, "score", "running")
            step_start = time.perf_counter()
            analysis.score, analysis.skill_analysis = await self._match_and_score(
                cv_extracted, jd_extracted
            )
            step_ms = (time.perf_counter() - step_start) * 1000
            logger.info(
                "Step 2 DONE (score): %.0fms — overall=%.1f",
                step_ms,
                analysis.score.overall,
            )
            await self._analysis_repo.update(analysis)
            self._publish_step(analysis_id, "score", "done", step_ms)

            # Step 3: Rewrite CV
            self._publish_step(analysis_id, "rewrite", "running")
            step_start = time.perf_counter()
            analysis.rewritten_cv = await self._ai_service.rewrite_cv(
                analysis.cv_text, analysis.jd_text, cv_extracted, jd_extracted
            )
            step_ms = (time.perf_counter() - step_start) * 1000
            logger.info("Step 3 DONE (rewrite): %.0fms", step_ms)
            await self._analysis_repo.update(analysis)
            self._publish_step(analysis_id, "rewrite", "done", step_ms)

            # Step 4: Truth-Anchoring
            self._publish_step(analysis_id, "truthcheck", "running")
            step_start = time.perf_counter()
            analysis.hallucination_report = await self._check_truth(
                analysis.cv_text, analysis.rewritten_cv, cv_extracted
            )
            step_ms = (time.perf_counter() - step_start) * 1000
            logger.info(
                "Step 4 DONE (truth-check): %.0fms — warnings=%d, safe=%s",
                step_ms,
                len(analysis.hallucination_report.warnings),
                analysis.hallucination_report.is_safe,
            )
            await self._analysis_repo.update(analysis)
            self._publish_step(analysis_id, "truthcheck", "done", step_ms)

            # Step 5: Visual Diff
            self._publish_step(analysis_id, "diff", "running")
            step_start = time.perf_counter()
            analysis.diff_result = self._compute_diff(
                analysis.cv_text, analysis.rewritten_cv
            )
            step_ms = (time.perf_counter() - step_start) * 1000
            logger.info(
                "Step 5 DONE (diff): %.0fms — segments=%d",
                step_ms,
                len(analysis.diff_result.segments),
            )
            await self._analysis_repo.update(analysis)
            self._publish_step(analysis_id, "diff", "done", step_ms)

            analysis.mark_completed()
            total_ms = (time.perf_counter() - pipeline_start) * 1000
            logger.info("Pipeline COMPLETE: analysis_id=%s, total=%.0fms", analysis_id, total_ms)

            # Publish pipeline complete event
            self._publish_step(analysis_id, "pipeline", "done", total_ms)

        except Exception as e:
            analysis.mark_failed()
            total_ms = (time.perf_counter() - pipeline_start) * 1000
            logger.error(
                "Pipeline FAILED: analysis_id=%s at %.0fms — %s",
                analysis_id, total_ms, str(e),
                exc_info=True,
            )
            self._publish_step(analysis_id, "pipeline", "failed", total_ms)
            raise

        await self._analysis_repo.update(analysis)
        return analysis

    async def _match_and_score(
        self, cv_extracted: dict, jd_extracted: dict
    ) -> tuple[MatchScore, SkillAnalysis]:
        """Match CV against JD using embeddings + cosine similarity."""

        cv_skills = set(s.lower() for s in cv_extracted.get("skills", []))
        jd_required = set(s.lower() for s in jd_extracted.get("required_skills", []))
        jd_preferred = set(s.lower() for s in jd_extracted.get("preferred_skills", []))
        all_jd_skills = jd_required | jd_preferred

        # Direct string matching first
        matched = cv_skills & all_jd_skills
        missing = all_jd_skills - cv_skills
        extra = cv_skills - all_jd_skills

        # Use embeddings for semantic matching of remaining skills
        if missing and extra:
            missing, extra, semantic_matched = await self._semantic_match(
                list(missing), list(extra)
            )
            matched = matched | semantic_matched

        # Calculate scores
        total_jd = len(all_jd_skills) if all_jd_skills else 1
        skills_score = min(100.0, (len(matched) / total_jd) * 100)

        # Experience & tools scores via embedding similarity
        cv_exp_text = " ".join(cv_extracted.get("experience", []))
        jd_exp_text = " ".join(jd_extracted.get("experience_requirements", []))
        cv_tools_text = " ".join(cv_extracted.get("tools", []))
        jd_tools_text = " ".join(jd_extracted.get("tools", []))

        exp_score = 50.0
        tools_score = 50.0
        if cv_exp_text and jd_exp_text:
            emb = await self._ai_service.get_embeddings([cv_exp_text, jd_exp_text])
            exp_score = self._cosine_sim(emb[0], emb[1]) * 100
        if cv_tools_text and jd_tools_text:
            emb = await self._ai_service.get_embeddings([cv_tools_text, jd_tools_text])
            tools_score = self._cosine_sim(emb[0], emb[1]) * 100

        overall = skills_score * 0.5 + exp_score * 0.3 + tools_score * 0.2

        score = MatchScore(
            overall=round(overall, 1),
            skills_score=round(skills_score, 1),
            experience_score=round(exp_score, 1),
            tools_score=round(tools_score, 1),
        )

        skill_analysis = SkillAnalysis(
            matched_skills=[Skill(name=s) for s in matched],
            missing_skills=[Skill(name=s) for s in missing],
            extra_skills=[Skill(name=s) for s in extra],
        )

        logger.debug(
            "Score breakdown: skills=%.1f, exp=%.1f, tools=%.1f → overall=%.1f",
            skills_score, exp_score, tools_score, overall,
        )

        return score, skill_analysis

    async def _semantic_match(
        self, missing: List[str], extra: List[str], threshold: float = 0.75
    ) -> tuple[set, set, set]:
        """Use embeddings to find semantically similar skills."""

        all_texts = missing + extra
        embeddings = await self._ai_service.get_embeddings(all_texts)

        missing_embs = embeddings[: len(missing)]
        extra_embs = embeddings[len(missing) :]

        semantic_matched = set()
        still_missing = set(missing)
        still_extra = set(extra)

        for i, m_skill in enumerate(missing):
            for j, e_skill in enumerate(extra):
                sim = self._cosine_sim(missing_embs[i], extra_embs[j])
                if sim >= threshold:
                    semantic_matched.add(m_skill)
                    still_missing.discard(m_skill)
                    still_extra.discard(e_skill)
                    break

        logger.debug(
            "Semantic match: %d matched, %d still missing, %d extra",
            len(semantic_matched), len(still_missing), len(still_extra),
        )
        return still_missing, still_extra, semantic_matched

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        a_arr = np.array(a)
        b_arr = np.array(b)
        dot = np.dot(a_arr, b_arr)
        norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
        return float(dot / norm) if norm > 0 else 0.0

    async def _check_truth(
        self, original: str, rewritten: str, cv_extracted: dict
    ) -> HallucinationReport:
        """Check rewritten CV for hallucinations."""

        warnings_data = await self._ai_service.check_hallucination(
            original, rewritten, cv_extracted
        )

        warnings = []
        for w in warnings_data:
            level_str = w.get("level", "medium").lower()
            level = WarningLevel(level_str) if level_str in [e.value for e in WarningLevel] else WarningLevel.MEDIUM
            warnings.append(
                HallucinationWarning(
                    section=w.get("section", ""),
                    original_text=w.get("original_text", ""),
                    rewritten_text=w.get("rewritten_text", ""),
                    issue_type=w.get("issue_type", "hallucination"),
                    explanation=w.get("explanation", ""),
                    level=level,
                )
            )

        is_safe = not any(w.level == WarningLevel.HIGH for w in warnings)
        return HallucinationReport(warnings=warnings, is_safe=is_safe)

    @staticmethod
    def _compute_diff(original: str, rewritten: str) -> DiffResult:
        """Compute visual diff between original and rewritten CV."""

        segments = []
        differ = difflib.SequenceMatcher(None, original.split(), rewritten.split())

        for tag, i1, i2, j1, j2 in differ.get_opcodes():
            if tag == "equal":
                text = " ".join(original.split()[i1:i2])
                segments.append(DiffSegment(text=text, diff_type=DiffType.UNCHANGED))
            elif tag == "replace":
                old_text = " ".join(original.split()[i1:i2])
                new_text = " ".join(rewritten.split()[j1:j2])
                segments.append(DiffSegment(text=old_text, diff_type=DiffType.REMOVED))
                segments.append(DiffSegment(text=new_text, diff_type=DiffType.ADDED))
            elif tag == "delete":
                text = " ".join(original.split()[i1:i2])
                segments.append(DiffSegment(text=text, diff_type=DiffType.REMOVED))
            elif tag == "insert":
                text = " ".join(rewritten.split()[j1:j2])
                segments.append(DiffSegment(text=text, diff_type=DiffType.ADDED))

        return DiffResult(segments=segments)
