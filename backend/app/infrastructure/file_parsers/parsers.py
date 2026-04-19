import fitz  # pymupdf
from docx import Document

from app.application.interfaces.file_parser import IFileParser


class PDFParser(IFileParser):
    """Parse PDF files using PyMuPDF."""

    async def parse(self, file_path: str) -> str:
        doc = fitz.open(file_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)

    def supports(self, filename: str) -> bool:
        return filename.lower().endswith(".pdf")


class DocxParser(IFileParser):
    """Parse DOCX files using python-docx."""

    async def parse(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs if para.text.strip())

    def supports(self, filename: str) -> bool:
        return filename.lower().endswith(".docx")


class PlainTextParser(IFileParser):
    """Parse plain text and markdown files."""

    async def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as source:
            return source.read()

    def supports(self, filename: str) -> bool:
        normalized = filename.lower()
        return normalized.endswith(".txt") or normalized.endswith(".md")


def get_parser(filename: str) -> IFileParser:
    """Factory to select appropriate file parser."""

    parsers = [PDFParser(), DocxParser(), PlainTextParser()]
    for parser in parsers:
        if parser.supports(filename):
            return parser
    raise ValueError(f"Unsupported file type: {filename}")
