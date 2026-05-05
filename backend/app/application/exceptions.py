"""Application-layer exception types."""


class AIProviderEmptyResponseError(RuntimeError):
    """Raised when an AI provider completes without returning usable text."""


class DocumentExtractionError(RuntimeError):
    """Raised when a file cannot be parsed into usable text.

    Used by ``services/shared/document_extractor.py`` so route handlers
    can map this to a 400 response without catching bare ``Exception``.
    """


class InsufficientJDError(ValueError):
    """Raised when a Job Description is unusable for downstream work.

    Examples: empty text, JD too short to extract any must-have keywords,
    LLM returned a completely empty structure. The generator refuses to
    fabricate content; routes should surface this as a 400.
    """
