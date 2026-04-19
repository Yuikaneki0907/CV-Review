import io
import os
import zipfile
from dataclasses import dataclass
from typing import Iterable

from fastapi import HTTPException, UploadFile


@dataclass
class UploadMeta:
    filename: str
    extension: str
    detected_type: str
    file_size: int


def _normalize_extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def _detect_type(file_bytes: bytes, filename: str) -> str | None:
    normalized_name = (filename or "").lower()
    if file_bytes.startswith(b"%PDF-"):
        return "pdf"

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" in names and any(name.startswith("word/") for name in names):
                return "docx"
    except zipfile.BadZipFile:
        pass

    if normalized_name.endswith(".txt"):
        return "txt"
    if normalized_name.endswith(".md"):
        return "md"

    return None


def validate_upload_bytes(
    *,
    filename: str,
    file_bytes: bytes,
    allowed_types: Iterable[str],
    max_size_mb: int,
    detail: str,
) -> UploadMeta:
    if not filename:
        raise HTTPException(status_code=400, detail="Tên file là bắt buộc")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File upload đang trống")

    max_bytes = max_size_mb * 1024 * 1024
    file_size = len(file_bytes)
    if file_size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File vượt quá giới hạn {max_size_mb}MB",
        )

    normalized_allowed = set(allowed_types)
    detected_type = _detect_type(file_bytes, filename)
    if detected_type is None or detected_type not in normalized_allowed:
        raise HTTPException(status_code=400, detail=detail)

    return UploadMeta(
        filename=filename,
        extension=_normalize_extension(filename),
        detected_type=detected_type,
        file_size=file_size,
    )


async def read_and_validate_upload(
    upload: UploadFile,
    *,
    allowed_types: Iterable[str],
    max_size_mb: int,
    detail: str,
) -> tuple[bytes, UploadMeta]:
    file_bytes = await upload.read()
    meta = validate_upload_bytes(
        filename=upload.filename or "",
        file_bytes=file_bytes,
        allowed_types=allowed_types,
        max_size_mb=max_size_mb,
        detail=detail,
    )
    return file_bytes, meta
