"""Phase 0 — skill / keyword normalisation tests."""
from __future__ import annotations

from app.application.services.shared.skill_normalisation import (
    normalize_skill_token,
    normalize_skill_tokens,
)


class TestNormaliseSingleToken:
    def test_lowercases_and_trims(self) -> None:
        assert normalize_skill_token("  Python  ") == "python"

    def test_collapses_whitespace(self) -> None:
        assert normalize_skill_token("Tailwind   CSS") == "tailwind css"

    def test_strips_trailing_punctuation(self) -> None:
        assert normalize_skill_token("React.") == "react"
        assert normalize_skill_token("Node.js,") == "node.js"

    def test_applies_alias_for_react_variants(self) -> None:
        for variant in ("React", "REACT", "react.js", "ReactJS"):
            assert normalize_skill_token(variant) == "react"

    def test_applies_alias_for_postgres_variants(self) -> None:
        for variant in ("Postgres", "PostgreSQL", "postgre sql"):
            assert normalize_skill_token(variant) == "postgresql"

    def test_unknown_token_passes_through(self) -> None:
        assert normalize_skill_token("Rust") == "rust"

    def test_empty_input_returns_empty(self) -> None:
        assert normalize_skill_token("") == ""
        assert normalize_skill_token("   ") == ""
        assert normalize_skill_token(None) == ""  # type: ignore[arg-type]


class TestNormaliseList:
    def test_deduplicates_preserving_order(self) -> None:
        assert normalize_skill_tokens(
            ["React", "React.js", "Python", "REACT", "Python"]
        ) == ["react", "python"]

    def test_drops_empty_results(self) -> None:
        assert normalize_skill_tokens(["", "  ", "Python", None]) == ["python"]  # type: ignore[list-item]

    def test_handles_none_input(self) -> None:
        assert normalize_skill_tokens(None) == []  # type: ignore[arg-type]
