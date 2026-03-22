from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.domain.entities.user import User
from app.domain.entities.analysis_result import AnalysisResult
from app.domain.entities.cv_file import CVFile


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

