import os
import re
from io import BytesIO

import mammoth
from docx import Document
from docx.document import Document as DocumentType
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from pdf2docx import Converter


def convert_pdf_to_docx(pdf_path: str, docx_path: str) -> None:
    converter = Converter(pdf_path)
    try:
        converter.convert(docx_path)
    finally:
        converter.close()


def build_import_preview_payload(docx_path: str) -> dict[str, str]:
    with open(docx_path, "rb") as source:
        docx_bytes = source.read()

    return {
        "markdown": _docx_to_markdown(docx_path),
        "html": _docx_to_html(docx_bytes),
    }


def _docx_to_html(docx_bytes: bytes) -> str:
    result = mammoth.convert_to_html(BytesIO(docx_bytes))
    html = (result.value or "").strip()
    return html or "<p></p>"


def _docx_to_markdown(docx_path: str) -> str:
    document = Document(docx_path)
    blocks: list[str] = []

    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            block_text = _paragraph_to_markdown(block)
        else:
            block_text = _table_to_markdown(block)

        if block_text:
            blocks.append(block_text)
        elif blocks and blocks[-1] != "":
            blocks.append("")

    compacted: list[str] = []
    for item in blocks:
        if item == "" and compacted and compacted[-1] == "":
            continue
        compacted.append(item)

    return "\n\n".join(part for part in compacted if part is not None).strip()


def _iter_block_items(parent: DocumentType):
    parent_element = parent.element.body
    for child in parent_element.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _paragraph_to_markdown(paragraph: Paragraph) -> str:
    text = _normalize_text(paragraph.text)
    if not text:
        return ""

    style_name = (paragraph.style.name or "").lower() if paragraph.style else ""
    heading_match = re.search(r"heading\s*(\d+)", style_name)
    if heading_match:
        level = max(1, min(int(heading_match.group(1)), 3))
        return f"{'#' * level} {text}"

    if "list bullet" in style_name or style_name.startswith("bullet"):
        return f"- {text}"

    if "list number" in style_name or "number" in style_name:
        return f"1. {text}"

    if _looks_like_heading(text):
        return f"## {text.title()}"

    return text


def _table_to_markdown(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells = [_normalize_text(cell.text).replace("|", "\\|") for cell in row.cells]
        if any(cells):
            rows.append(cells)

    if not rows:
        return ""

    if len(rows[0]) == 1:
        return "\n".join(row[0] for row in rows if row and row[0])

    header = rows[0]
    divider = ["---"] * len(header)
    body = rows[1:] or []

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(divider) + " |",
    ]
    for row in body:
        normalized = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(normalized[: len(header)]) + " |")
    return "\n".join(lines)


def _looks_like_heading(text: str) -> bool:
    if len(text) > 80:
        return False
    upper_ratio = sum(1 for ch in text if ch.isupper()) / max(1, sum(1 for ch in text if ch.isalpha()))
    return upper_ratio > 0.6 or text.endswith(":")


def _normalize_text(value: str) -> str:
    value = (value or "").replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()
