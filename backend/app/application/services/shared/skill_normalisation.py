"""Skill / keyword token normalisation.

Single source of truth — replaces the ``SKILL_ALIASES`` dict and
``normalize_skill_name`` function previously embedded in
``application/use_cases/analyze_cv.py``.

The generator (Phase 2), the JD extractor, the CV extractor, and the
keyword-coverage scorer (Phase 1) all run their tokens through this
module so comparisons are apples-to-apples.
"""
from __future__ import annotations

import re

# Lower-case canonical forms. Keys are common spellings; values are the
# canonical token the rest of the system stores and compares against.
SKILL_ALIASES: dict[str, str] = {
    # JavaScript ecosystem
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "react.js": "react",
    "reactjs": "react",
    "react": "react",
    "node.js": "node.js",
    "nodejs": "node.js",
    "node": "node.js",
    "next.js": "next.js",
    "nextjs": "next.js",
    # Python ecosystem
    "fast api": "fastapi",
    "fastapi": "fastapi",
    "django": "django",
    "flask": "flask",
    # Databases
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "postgre sql": "postgresql",
    "ms sql": "sql server",
    "mssql": "sql server",
    "sqlserver": "sql server",
    "sql server": "sql server",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    # CSS frameworks
    "tailwindcss": "tailwind css",
    "tailwind": "tailwind css",
    "tailwind css": "tailwind css",
    # DevOps / CI
    "ci/cd": "ci cd",
    "cicd": "ci cd",
    "ci cd": "ci cd",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    # ML / Data
    "ml": "machine learning",
    "machine learning": "machine learning",
    "deep learning": "deep learning",
    "dl": "deep learning",
    "nlp": "nlp",
    "computer vision": "computer vision",
    "cv": "computer vision",  # only when context is ML — see disambiguation note below
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
}

# Tokens we explicitly do NOT collapse via the alias map because they are
# ambiguous in this domain (e.g. "cv" → "computer vision" would mangle
# resume-tooling text). Used by tests; not enforced at runtime.
_AMBIGUOUS_TOKENS = frozenset({"cv"})


def normalize_skill_token(value: str) -> str:
    """Normalise a single skill string to its canonical form.

    Lower-cases, collapses whitespace, strips trailing punctuation,
    then applies the alias map. Unknown tokens pass through unchanged
    (lower-cased + trimmed) so downstream comparisons still work.

    Args:
        value: Raw skill string, may be None/empty/messy.

    Returns:
        Canonical lower-case token, or empty string if the input had
        no usable characters.
    """
    if not value:
        return ""
    normalized = re.sub(r"\s+", " ", str(value).strip().lower())
    normalized = normalized.strip(" .,/|;:")
    if not normalized:
        return ""
    return SKILL_ALIASES.get(normalized, normalized)


def normalize_skill_tokens(values: list[str]) -> list[str]:
    """Normalise a list of skill strings.

    De-duplicates while preserving the first-seen order, drops empty
    results.
    """
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        token = normalize_skill_token(value)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out
