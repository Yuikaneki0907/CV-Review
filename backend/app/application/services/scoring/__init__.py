"""Five-dimension CV scorer.

Public entry point: :func:`score_cv`. Each dimension lives in its own
module so it can be unit-tested in isolation; the aggregator combines
them into an :class:`AnalysisResultSchema`.
"""

from app.application.services.scoring.aggregator import score_cv

__all__ = ["score_cv"]
