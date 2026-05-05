"""Phase 0 — document extractor tests.

PDF generation uses pymupdf directly (already a project dep) so we don't
need fixture files on disk.
"""
from __future__ import annotations

import asyncio
import io

import fitz
import pytest
from docx import Document

from app.application.exceptions import DocumentExtractionError
from app.application.services.shared.document_extractor import (
    extract_document_text,
    remove_tempfile,
    write_to_tempfile,
)


def _make_pdf_bytes(body: str) -> bytes:
    """Build a single-page PDF.

    ``insert_text`` writes one line; the helper splits ``body`` on
    newlines so the test can exercise multi-line extraction.
    """
    doc = fitz.open()
    page = doc.new_page()
    y = 72.0
    for line in body.splitlines() or [body]:
        page.insert_text((72, y), line)
        y += 14
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for line in paragraphs:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _run(coro):
    return asyncio.run(coro)


class TestExtractDocumentTextPDF:
    def test_happy_pdf_extracts_text_and_marks_quality(self) -> None:
        # 30 separate lines so each fits on the page; total >200 chars.
        body = "\n".join(["Senior Backend Engineer."] * 30)
        result = _run(extract_document_text(_make_pdf_bytes(body), "cv.pdf"))
        assert result.extension == "pdf"
        assert "Senior Backend Engineer" in result.text
        assert result.page_count == 1
        assert result.extraction_quality == "high"
        assert result.warnings == []

    def test_empty_pdf_is_flagged_low_quality(self) -> None:
        result = _run(extract_document_text(_make_pdf_bytes(""), "blank.pdf"))
        assert result.extension == "pdf"
        assert result.extraction_quality == "low"
        assert any("pdf yielded" in w for w in result.warnings)


class TestExtractDocumentTextDOCX:
    def test_docx_extracts_paragraphs(self) -> None:
        body = ["Heading", "First paragraph " * 30, "Second paragraph " * 30]
        result = _run(extract_document_text(_make_docx_bytes(body), "cv.docx"))
        assert result.extension == "docx"
        assert "First paragraph" in result.text
        assert result.extraction_quality == "high"
        assert result.page_count is None


class TestExtractDocumentTextPlaintext:
    def test_txt_decodes_utf8(self) -> None:
        payload = ("Vietnamese: kỹ năng. " * 30).encode("utf-8")
        result = _run(extract_document_text(payload, "notes.txt"))
        assert result.extension == "txt"
        assert "kỹ năng" in result.text
        assert result.extraction_quality == "high"

    def test_md_decoded(self) -> None:
        payload = b"# Heading\n" + b"body text " * 30
        result = _run(extract_document_text(payload, "doc.md"))
        assert result.extension == "md"
        assert "Heading" in result.text


class TestExtractDocumentTextErrors:
    def test_unsupported_extension_raises(self) -> None:
        with pytest.raises(DocumentExtractionError):
            _run(extract_document_text(b"hello", "image.png"))

    def test_garbage_pdf_raises(self) -> None:
        with pytest.raises(DocumentExtractionError):
            _run(extract_document_text(b"not a pdf at all", "broken.pdf"))


class TestTempfileHelpers:
    def test_write_and_remove_tempfile_round_trip(self) -> None:
        path = write_to_tempfile(b"hello", "pdf")
        try:
            with open(path, "rb") as f:
                assert f.read() == b"hello"
        finally:
            remove_tempfile(path)
        # Removing again is a no-op (best-effort cleanup).
        remove_tempfile(path)
