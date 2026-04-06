from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class CVFile:
    """Domain entity representing a stored CV file version."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    analysis_id: Optional[UUID] = None

    original_filename: str = ""
    storage_key: str = ""          # MinIO object key, e.g. "{user_id}/{file_id}.pdf"
    content_type: str = ""
    file_size: int = 0
    version: int = 1               # auto-incremented per user + filename

    created_at: datetime = field(default_factory=datetime.utcnow)
