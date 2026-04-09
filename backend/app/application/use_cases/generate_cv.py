from uuid import UUID

from app.domain.entities.generated_cv import GeneratedCV
from app.application.interfaces.repositories import IGeneratedCVRepository
from app.application.interfaces.ai_service import IAIService
from app.logger import get_logger

logger = get_logger("app.application.use_cases.generate_cv")

class GenerateCVUseCase:
    """Orchestrator for the CV generation feature."""

    def __init__(
        self,
        cv_repo: IGeneratedCVRepository,
        ai_service: IAIService,
    ):
        self._cv_repo = cv_repo
        self._ai_service = ai_service

    async def execute(
        self,
        user_id: UUID,
        job_title: str,
        jd_text: str,
        level: str,
        output_format: str = "markdown",
    ) -> GeneratedCV:
        """Run the AI prompt to generate a CV template and save it to DB."""
        
        logger.info(
            "Generating CV for user_id=%s, job_title=%s, level=%s, output_format=%s",
            user_id,
            job_title,
            level,
            output_format,
        )
        
        # 1. Ask AI to generate CV template in requested output format
        cv_content = await self._ai_service.generate_cv_template(
            job_title=job_title,
            jd_text=jd_text,
            level=level,
            output_format=output_format,
        )
        
        # 2. Store in JSON format
        generated_content = {
            "content": cv_content,
            "format": output_format,
        }
        if output_format in {"markdown", "docx"}:
            generated_content["markdown"] = cv_content
        else:
            generated_content["text"] = cv_content
        
        # 3. Save to database
        cv_entity = GeneratedCV(
            user_id=user_id,
            target_jd_text=jd_text,
            base_profile_data={"job_title": job_title, "level": level},
            generated_content=generated_content,
            status="completed"
        )
        
        saved_cv = await self._cv_repo.create(cv_entity)
        logger.info("Generated CV saved successfully: cv_id=%s", saved_cv.id)
        
        return saved_cv
