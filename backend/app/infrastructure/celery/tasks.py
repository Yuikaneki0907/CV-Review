import asyncio
import time
from uuid import UUID

from app.infrastructure.celery import celery_app
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.ai.openai_service import OpenAIService
from app.application.use_cases.analyze_cv import AnalyzeCVUseCase
from app.logger import get_logger

logger = get_logger("app.infrastructure.celery.tasks")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_analysis_task(self, analysis_id: str):
    """Celery task that runs the full CV analysis pipeline."""

    logger.info("Task START: analysis_id=%s, task_id=%s", analysis_id, self.request.id)

    async def _run():
        start = time.perf_counter()
        async with async_session_factory() as session:
            analysis_repo = AnalysisRepository(session)
            ai_service = OpenAIService()
            use_case = AnalyzeCVUseCase(analysis_repo, ai_service)

            try:
                await use_case.execute(UUID(analysis_id))
                await session.commit()
                duration = (time.perf_counter() - start) * 1000
                logger.info(
                    "Task SUCCESS: analysis_id=%s, duration=%.0fms",
                    analysis_id, duration,
                )
            except Exception as e:
                await session.rollback()
                duration = (time.perf_counter() - start) * 1000
                logger.error(
                    "Task FAILED: analysis_id=%s, duration=%.0fms, error=%s",
                    analysis_id, duration, str(e),
                    exc_info=True,
                )
                raise self.retry(exc=e)

    asyncio.run(_run())
