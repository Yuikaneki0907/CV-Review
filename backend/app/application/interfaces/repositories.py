from datetime import datetime
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.domain.entities.user import User
from app.domain.entities.password_reset_token import PasswordResetToken
from app.domain.entities.analysis_result import AnalysisResult
from app.domain.entities.cv_file import CVFile
from app.domain.entities.generated_cv import GeneratedCV


class IUserRepository(ABC):
    """Port for user data access."""

    @abstractmethod
    async def create(self, user: User) -> User:
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    @abstractmethod
    async def update(self, user_id: UUID, full_name: Optional[str] = None, phone_number: Optional[str] = None) -> Optional[User]:
        ...

    @abstractmethod
    async def update_password_hash(self, user_id: UUID, password_hash: str) -> Optional[User]:
        ...

    @abstractmethod
    async def create_password_reset_token(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        ...

    @abstractmethod
    async def get_valid_password_reset_token(self, token_hash: str) -> Optional[PasswordResetToken]:
        ...

    @abstractmethod
    async def invalidate_password_reset_tokens(self, user_id: UUID) -> None:
        ...


class IAnalysisRepository(ABC):
    """Port for analysis data access."""

    @abstractmethod
    async def create(self, analysis: AnalysisResult) -> AnalysisResult:
        ...

    @abstractmethod
    async def get_by_id(self, analysis_id: UUID) -> Optional[AnalysisResult]:
        ...

    @abstractmethod
    async def update(self, analysis: AnalysisResult) -> AnalysisResult:
        ...

    @abstractmethod
    async def get_by_user_id(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> List[AnalysisResult]:
        ...

    @abstractmethod
    async def get_stuck_analyses(self) -> List[AnalysisResult]:
        """Return all analyses with status PENDING or PROCESSING (stuck after crash)."""
        ...

    @abstractmethod
    async def soft_delete(self, analysis_id: UUID, user_id: UUID) -> bool:
        ...


class ICVFileRepository(ABC):
    """Port for CV file version data access."""

    @abstractmethod
    async def create(self, cv_file: CVFile) -> CVFile:
        ...

    @abstractmethod
    async def get_by_id(self, file_id: UUID) -> Optional[CVFile]:
        ...

    @abstractmethod
    async def list_by_user_id(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> List[CVFile]:
        ...

    @abstractmethod
    async def get_next_version(self, user_id: UUID, filename: str) -> int:
        """Return the next version number for a given user + filename combo."""
        ...

    @abstractmethod
    async def soft_delete(self, file_id: UUID, user_id: UUID) -> bool:
        ...


class IGeneratedCVRepository(ABC):
    """Port for GeneratedCV entity database operations."""

    @abstractmethod
    async def create(self, cv: "GeneratedCV") -> "GeneratedCV":
        ...

    @abstractmethod
    async def create_versioned(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
        parent_version_id: UUID,
        target_jd_text: Optional[str],
        base_profile_data: Optional[dict],
        generated_content: dict,
        status: str,
    ) -> "GeneratedCV":
        ...

    @abstractmethod
    async def get_by_id(self, cv_id: UUID) -> Optional["GeneratedCV"]:
        ...

    @abstractmethod
    async def list_by_user_id(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> List["GeneratedCV"]:
        ...

    @abstractmethod
    async def update_generated_content(
        self,
        cv_id: UUID,
        user_id: UUID,
        generated_content: dict,
    ) -> Optional["GeneratedCV"]:
        ...

    @abstractmethod
    async def get_next_version(self, user_id: UUID, conversation_id: UUID) -> int:
        ...

    @abstractmethod
    async def list_versions(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> List["GeneratedCV"]:
        ...

    @abstractmethod
    async def soft_delete(self, cv_id: UUID, user_id: UUID) -> bool:
        ...
