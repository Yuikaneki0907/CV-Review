from app.application.interfaces.ai_service import IAIService
from app.infrastructure.ai.gemini_service import GeminiService
from app.infrastructure.ai.openai_service import OpenAIService
from app.config import get_settings

def ai_service_factory() -> IAIService:
    """Factory to create the AI service based on configuration."""
    settings = get_settings()
    provider = settings.AI_PROVIDER.lower()

    if provider == "openai_oauth":
        return OpenAIService(is_oauth=True)
    elif provider == "openai":
        return OpenAIService(is_oauth=False)
    elif provider == "gemini":
        return GeminiService()
    
    # Fallback to Gemini
    return GeminiService()
