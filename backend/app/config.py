from typing import List

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CV Review API"
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:3020"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cvreview:cvreview_pass@db:5432/cvreview"

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@cvreview.local"
    SMTP_FROM_NAME: str = "CV Review"
    SMTP_USE_TLS: bool = True

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"

    # OpenAI OAuth (Special)
    OPENAI_API_KEY_OAUTH: str = ""
    OPENAI_API_BASE_OAUTH: str = "http://127.0.0.1:8317/v1"
    OPENAI_MODEL_OAUTH: str = "gpt-5.4"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_GEN_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"

    # AI Provider
    AI_PROVIDER: str = "openai"  # values: "openai", "gemini", "openai_oauth"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3020", "http://localhost:5120"]

    # File upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "cv-files"
    MINIO_USE_SSL: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
