"""CV generation services.

Public entry point: :func:`generate_cv`. The generator wraps the
:class:`IAIService` template call with prompt assembly + light
post-processing so the use case stays orchestration-only.
"""

from app.application.services.generation.cv_generator import (
    GenerationOutput,
    build_profile_section,
    format_guide_for,
    generate_cv,
)
from app.application.services.generation.cv_reviser import (
    RevisionOutput,
    revise_cv,
)
from app.application.services.generation.improvement_loop import (
    DEFAULT_MAX_ITERATIONS,
    LoopOutcome,
    run_improvement_loop,
    run_improvement_loop_events,
)

__all__ = [
    "DEFAULT_MAX_ITERATIONS",
    "GenerationOutput",
    "LoopOutcome",
    "RevisionOutput",
    "build_profile_section",
    "format_guide_for",
    "generate_cv",
    "revise_cv",
    "run_improvement_loop",
    "run_improvement_loop_events",
]
