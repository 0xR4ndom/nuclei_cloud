import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import redis.asyncio as aioredis

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.api.v1 import api_router

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


# ── Global error handler ────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import traceback
    import uuid as _uuid

    error_id = str(_uuid.uuid4())[:8]
    logger.error(
        f"[error:{error_id}] Unhandled exception on {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_id": error_id,
        },
    )


# ── Health check (deep) ──────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health():
    """
    Deep health check used by Docker/k8s probes.
    Returns 200 only when DB, Redis, and nuclei binary are all reachable.
    """
    checks: dict = {}
    healthy = True

    # 1. Database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"
        healthy = False

    # 2. Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        healthy = False

    # 3. Nuclei binary
    nuclei_ok = os.path.isfile(settings.NUCLEI_BINARY) and os.access(
        settings.NUCLEI_BINARY, os.X_OK
    )
    checks["nuclei"] = "ok" if nuclei_ok else "binary not found or not executable"
    if not nuclei_ok:
        healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if healthy else "degraded",
            "version": settings.APP_VERSION,
            "checks": checks,
        },
    )
