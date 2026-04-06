import asyncio
import time
from uuid import UUID

import redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.celery import celery_app
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.ai.openai_service import OpenAIService
from app.application.use_cases.analyze_cv import AnalyzeCVUseCase
from app.config import get_settings
from app.logger import get_logger

logger = get_logger("app.infrastructure.celery.tasks")


def _get_redis_client():
    """Create a synchronous Redis client for pub/sub."""
    settings = get_settings()
    # Parse redis URL (redis://localhost:6379/0)
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_analysis_task(self, analysis_id: str):
    """Celery task that runs the full CV analysis pipeline."""

    logger.info("Task START: analysis_id=%s, task_id=%s", analysis_id, self.request.id)

    async def _run():
        # Create a dedicated engine + session for this task invocation
        # so that we never share asyncpg connections across concurrent tasks.
        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Create Redis client for step streaming
        redis_client = None
        try:
            redis_client = _get_redis_client()
            redis_client.ping()
            logger.info("Redis connected for step streaming")
        except Exception as e:
            logger.warning("Redis unavailable for streaming, proceeding without: %s", e)
            redis_client = None

        start = time.perf_counter()
        try:
            async with session_factory() as session:
                analysis_repo = AnalysisRepository(session)
                ai_service = OpenAIService()
                use_case = AnalyzeCVUseCase(analysis_repo, ai_service, redis_client)

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
        finally:
            await engine.dispose()
            if redis_client:
                redis_client.close()

    asyncio.run(_run())
