"""Extracted document schema — the output of the shared document parser."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentExtension = Literal["pdf", "docx", "txt", "md"]
ExtractionQuality = Literal["high", "low"]


class ExtractedDocument(BaseModel):
    """Result of parsing a single uploaded file.

    Attributes:
        text: Extracted plain text.
        extension: Normalised file extension without the dot.
        page_count: Page count for PDFs; None for other formats.
        extraction_quality: "low" when the text is very short or
            mostly whitespace — typically a scanned/empty PDF.
            Callers should refuse or warn before sending such text
            to an LLM.
        warnings: Human-readable diagnostics (e.g. "pdf yielded <200
            characters", "docx has no paragraphs").
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    extension: DocumentExtension
    page_count: int | None = None
    extraction_quality: ExtractionQuality = "high"
    warnings: list[str] = Field(default_factory=list)
