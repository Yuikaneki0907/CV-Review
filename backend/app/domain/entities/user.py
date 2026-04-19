from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class User:
    """User domain entity."""

    id: UUID = field(default_factory=uuid4)
    email: str = ""
    password_hash: str = ""
    full_name: str = ""
    phone_number: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
