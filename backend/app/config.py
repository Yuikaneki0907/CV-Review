from typing import List

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CV Review API"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5420/cv_review"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6320/0"
    CELERY_BROKER_URL: str = "redis://localhost:6320/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6320/0"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"

    # OpenAI OAuth (Special)
    OPENAI_API_KEY_OAUTH: str = "V0uLP652VOEfEfIJuOlsxM2B5cexiO5P"
    OPENAI_API_BASE_OAUTH: str = "http://127.0.0.1:8317/v1"
    OPENAI_MODEL_OAUTH: str = "gpt-5.4"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_GEN_MODEL: str = "gemini-3-flash-preview"
    GEMINI_EMBED_MODEL: str = "text-embedding-004"

    # AI Provider
    AI_PROVIDER: str = "openai_oauth"  # values: "openai", "gemini", "openai_oauth"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3020", "http://localhost:5120"]

    # File upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9020"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "cv-files"
    MINIO_USE_SSL: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
