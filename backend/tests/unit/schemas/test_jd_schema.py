"""Phase 0 — JDSchema contract tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.schemas import JDSchema


class TestJDSchemaHappyPath:
    def test_full_valid_input_round_trips(self) -> None:
        schema = JDSchema(
            raw_text="Looking for a Senior Backend Engineer...",
            job_title="Senior Backend Engineer",
            seniority="senior",
            must_have_keywords=["python", "fastapi", "postgresql"],
            nice_to_have_keywords=["redis"],
            tools=["docker", "aws"],
            responsibilities=["Design APIs", "Mentor juniors"],
            years_of_experience=5,
            domain="fintech",
        )
        assert schema.job_title == "Senior Backend Engineer"
        assert schema.is_usable is True
        # Round-trip through model_dump preserves all fields.
        assert JDSchema(**schema.model_dump()) == schema


class TestJDSchemaEmpty:
    def test_empty_factory_sets_warning(self) -> None:
        schema = JDSchema.empty("jd_extraction_failed")
        assert schema.must_have_keywords == []
        assert schema.extraction_warnings == ["jd_extraction_failed"]
        assert schema.is_usable is False

    def test_empty_factory_preserves_raw_text(self) -> None:
        schema = JDSchema.empty("jd_too_short", raw_text="too short")
        assert schema.raw_text == "too short"
        assert schema.is_usable is False


class TestJDSchemaConstraints:
    def test_frozen_blocks_mutation(self) -> None:
        schema = JDSchema(raw_text="...")
        with pytest.raises(ValidationError):
            schema.job_title = "Hacked"  # type: ignore[misc]

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JDSchema(raw_text="...", surprise_field="boom")  # type: ignore[call-arg]

    def test_unknown_seniority_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JDSchema(raw_text="...", seniority="overlord")  # type: ignore[arg-type]
