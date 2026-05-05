"""Phase 1 — structure dimension."""
from __future__ import annotations

from app.application.services.scoring import structure
from app.domain.schemas import CVBullet, CVExperienceEntry, CVSchema


def _full_cv() -> CVSchema:
    return CVSchema(
        raw_text="...",
        candidate_facts_present=True,
        placeholders_remaining=0,
        summary="A senior backend engineer.",
        skills=["python", "fastapi"],
        experience=[
            CVExperienceEntry(
                role="Eng",
                company="Acme",
                period="2022",
                bullets=[CVBullet(text="Built thing")],
            )
        ],
        education=["BS CS"],
    )


class TestStructureHappyPath:
    def test_all_sections_zero_placeholders_with_facts_scores_100(self) -> None:
        dim = structure.evaluate(_full_cv())
        assert dim.score == 100.0
        assert "4/4 core sections" in dim.reason


class TestStructureMissingSections:
    def test_missing_summary_reduces_score(self) -> None:
        cv = _full_cv().model_copy(update={"summary": ""})
        dim = structure.evaluate(cv)
        assert dim.score == 75.0  # 3/4 sections
        assert "summary" in dim.reason

    def test_missing_all_sections_scores_zero(self) -> None:
        cv = CVSchema(
            raw_text="...",
            candidate_facts_present=True,
            summary="",
            skills=[],
            experience=[],
            education=[],
        )
        dim = structure.evaluate(cv)
        assert dim.score == 0.0


class TestStructurePlaceholders:
    def test_few_placeholders_dock_score(self) -> None:
        cv = _full_cv().model_copy(update={"placeholders_remaining": 2})
        dim = structure.evaluate(cv)
        # 100 (sections) - 10 (2*5 placeholder penalty) = 90
        assert dim.score == 90.0

    def test_many_placeholders_capped_at_30(self) -> None:
        cv = _full_cv().model_copy(update={"placeholders_remaining": 50})
        dim = structure.evaluate(cv)
        # 100 - 30 (capped) = 70
        assert dim.score == 70.0


class TestStructureCandidateFacts:
    def test_no_candidate_facts_penalty(self) -> None:
        cv = _full_cv().model_copy(update={"candidate_facts_present": False})
        dim = structure.evaluate(cv)
        # 100 - 25 (facts penalty) = 75
        assert dim.score == 75.0
        assert "no concrete candidate facts" in dim.reason
