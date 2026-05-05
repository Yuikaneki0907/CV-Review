"""Tiny prompt-template loader.

Uses :class:`string.Template` (``$var``) rather than ``str.format``
because prompts routinely contain literal ``{`` / ``}`` characters
(JSON schemas, examples) that would break ``.format()``.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

_PROMPT_DIR = Path(__file__).parent


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """Load a prompt template by name (without extension).

    Args:
        name: File stem under ``prompts/``, e.g. ``"jd_extraction"``.

    Returns:
        Raw template text.

    Raises:
        FileNotFoundError: If no ``{name}.txt`` exists in the prompts
            directory.
    """
    path = _PROMPT_DIR / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **variables: object) -> str:
    """Render a prompt template by substituting ``$variable`` placeholders.

    Unknown placeholders are left intact (``safe_substitute``) so a
    typo in a variable name surfaces in the rendered prompt rather than
    raising at runtime — caller can spot it in logs and fix.

    Args:
        name: Template file stem.
        **variables: Substitution values; non-string values are
            ``str()``-coerced.

    Returns:
        Rendered prompt string ready to send to an LLM.
    """
    template = Template(load_prompt(name))
    return template.safe_substitute({k: str(v) for k, v in variables.items()})
