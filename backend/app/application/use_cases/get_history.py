from typing import List
from uuid import UUID

from app.domain.entities.analysis_result import AnalysisResult
from app.application.interfaces.repositories import IAnalysisRepository


class GetHistoryUseCase:
    """Get analysis history for a user."""

    def __init__(self, analysis_repo: IAnalysisRepository):
        self._analysis_repo = analysis_repo

    async def execute(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> List[AnalysisResult]:
        return await self._analysis_repo.get_by_user_id(user_id, limit, offset)
