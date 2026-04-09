from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict
from uuid import UUID, uuid4

@dataclass
class GeneratedCV:
    """Generated CV domain entity."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    
    target_jd_text: Optional[str] = None
    base_profile_data: Optional[Dict] = None
    
    generated_content: Dict = field(default_factory=dict)
    status: str = "draft"
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None
