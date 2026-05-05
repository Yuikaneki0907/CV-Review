"""Phase 0 — CVSchema contract tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.schemas import CVBullet, CVExperienceEntry, CVSchema, PLACEHOLDER_PATTERN


class TestCVSchemaHappyPath:
    def test_real_cv_is_not_template_only(self) -> None:
        schema = CVSchema(
            raw_text="real candidate cv",
            placeholders_remaining=0,
            candidate_facts_present=True,
            summary="5 years backend",
            skills=["python", "fastapi"],
            experience=[
                CVExperienceEntry(
                    role="Engineer",
                    company="Acme",
                    period="2022 - now",
                    bullets=[
                        CVBullet(
                            text="Built API serving 1M req/day",
                            has_action_verb=True,
                            has_metric=True,
                        )
                    ],
                )
            ],
        )
        assert schema.is_template_only is False


class TestCVSchemaTemplateDetection:
    def test_no_candidate_facts_is_template_only(self) -> None:
        schema = CVSchema(raw_text="x", candidate_facts_present=False)
        assert schema.is_template_only is True

    def test_many_placeholders_is_template_only(self) -> None:
        schema = CVSchema(
            raw_text="x",
            candidate_facts_present=True,  # even with facts...
            placeholders_remaining=6,  # ...too many placeholders flips it
        )
        assert schema.is_template_only is True

    def test_few_placeholders_with_facts_is_not_template(self) -> None:
        schema = CVSchema(
            raw_text="x",
            candidate_facts_present=True,
            placeholders_remaining=2,
        )
        assert schema.is_template_only is False


class TestCVSchemaConstraints:
    def test_frozen_blocks_mutation(self) -> None:
        schema = CVSchema(raw_text="...")
        with pytest.raises(ValidationError):
            schema.summary = "Hacked"  # type: ignore[misc]

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CVSchema(raw_text="...", boom=1)  # type: ignore[call-arg]


class TestPlaceholderPattern:
    def test_matches_square_bracket_placeholders(self) -> None:
        assert PLACEHOLDER_PATTERN.findall("[Họ và tên] [Email]") == [
            "[Họ và tên]",
            "[Email]",
        ]

    def test_matches_angle_bracket_placeholders(self) -> None:
        assert PLACEHOLDER_PATTERN.findall("Hello <TBD> world <name>") == [
            "<TBD>",
            "<name>",
        ]

    def test_does_not_match_url_brackets(self) -> None:
        # Markdown link text [foo](bar) — the [foo] portion is matched,
        # but a bare "[]" or single-char "[a]" should not be.
        assert PLACEHOLDER_PATTERN.findall("[]") == []
        assert PLACEHOLDER_PATTERN.findall("[a]") == []  # too short
