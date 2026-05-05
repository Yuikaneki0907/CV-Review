"""Externalised prompt templates.

Templates live as ``.txt`` files in this directory with
``string.Template`` style placeholders (``$variable`` or ``${variable}``).
Use ``render_prompt(name, **vars)`` to load and substitute.

This package replaces the inline prompt strings previously duplicated
across ``infrastructure/ai/gemini_service.py`` and
``infrastructure/ai/openai_service.py``. Phase 0 introduces JD/CV
extraction prompts; later phases will migrate the rest.
"""

from app.application.prompts.loader import load_prompt, render_prompt

__all__ = ["load_prompt", "render_prompt"]
