import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.api.v1 import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _create_admin_user():
    """Ensure a default admin exists on first boot."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash, generate_api_key
    from sqlalchemy import select
    import uuid

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == settings.FIRST_ADMIN_EMAIL)
        )
        if result.scalar_one_or_none():
            return

        admin = User(
            id=str(uuid.uuid4()),
            email=settings.FIRST_ADMIN_EMAIL,
            hashed_password=get_password_hash(settings.FIRST_ADMIN_PASSWORD),
            full_name="Administrator",
            role=UserRole.ADMIN,
            api_key=generate_api_key(),
        )
        session.add(admin)
        await session.commit()
        logger.info(f"Created default admin: {settings.FIRST_ADMIN_EMAIL}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables + seed admin
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _create_admin_user()

    # Ensure output dirs exist
    for d in [settings.NUCLEI_OUTPUT_DIR, settings.NUCLEI_CUSTOM_TEMPLATES_DIR]:
        os.makedirs(d, exist_ok=True)

    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} started")
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Nuclei Cloud — Distributed vulnerability scanner orchestrator",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Security middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
