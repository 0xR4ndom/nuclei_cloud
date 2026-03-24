from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Nuclei Cloud"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str
    ASYNC_DATABASE_URL: str = ""

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

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # First admin
    FIRST_ADMIN_EMAIL: str = "admin@nucleicloud.local"
    FIRST_ADMIN_PASSWORD: str = "changeme123!"

    model_config = {"env_file": ".env", "case_sensitive": True}

    def model_post_init(self, __context):
        if not self.ASYNC_DATABASE_URL:
            self.ASYNC_DATABASE_URL = self.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://"
            )


settings = Settings()
