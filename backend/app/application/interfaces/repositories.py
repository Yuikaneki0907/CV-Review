from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.domain.entities.user import User
from app.domain.entities.analysis_result import AnalysisResult


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
