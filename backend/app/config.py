import logging
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Nuclei Cloud"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Auth / JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str
    ASYNC_DATABASE_URL: str = ""
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Nuclei
    NUCLEI_BINARY: str = "/usr/local/bin/nuclei"
    NUCLEI_TEMPLATES_DIR: str = "/opt/nuclei-templates"
    NUCLEI_CUSTOM_TEMPLATES_DIR: str = "/opt/custom-templates"
    NUCLEI_OUTPUT_DIR: str = "/opt/nuclei-output"
    NUCLEI_RATE_LIMIT: int = 150
    NUCLEI_BULK_SIZE: int = 25
    NUCLEI_CONCURRENCY: int = 25

    # Scan limits
    SCAN_TIMEOUT_SECONDS: int = 3600          # Hard cap per scan (1 hour)
    MAX_TARGETS_PER_SCAN: int = 10_000        # Prevent runaway scans
    MAX_FINDINGS_PER_SCAN: int = 50_000       # Prevent disk exhaustion

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # First admin (used only on first boot)
    FIRST_ADMIN_EMAIL: str = "admin@nucleicloud.local"
    FIRST_ADMIN_PASSWORD: str = "changeme123!"

    model_config = {"env_file": ".env", "case_sensitive": True}

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long. "
                "Generate one with: openssl rand -hex 32"
            )
        if v == "change-me-in-production-use-openssl-rand-hex-32":
            raise ValueError(
                "SECRET_KEY is still set to the example value. "
                "Set a unique SECRET_KEY in your .env file."
            )
        return v

    def model_post_init(self, __context) -> None:
        if not self.ASYNC_DATABASE_URL:
            self.ASYNC_DATABASE_URL = self.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
        # Apply log level
        logging.basicConfig(level=getattr(logging, self.LOG_LEVEL.upper(), logging.INFO))


settings = Settings()
