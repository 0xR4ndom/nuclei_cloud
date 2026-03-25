"""
RBAC (Role-Based Access Control) integration tests.

Tests every role (ADMIN, ANALYST, VIEWER, unauthenticated, expired token)
against all key API endpoints using the in-memory SQLite test database.
"""
import uuid
import pytest
from httpx import AsyncClient

from app.models.user import User, UserRole
from app.models.scan import Scan, ScanStatus, ScanTargetList
from app.models.target import Target, TargetList, TargetType
from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create_other_user_scan(db: AsyncSession, other_user_id: str) -> str:
    """Create a scan owned by another user; returns the scan id."""
    scan = Scan(
        id=str(uuid.uuid4()),
        name="Other User Scan",
        status=ScanStatus.DONE,
        owner_id=other_user_id,
        config={},
        total_targets=0,
        total_findings=0,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan.id


# ── Auth endpoint tests ───────────────────────────────────────────────────────

async def test_login_valid_credentials(async_client: AsyncClient, admin_user: User):
    resp = await async_client.post("/api/v1/auth/login", json={
        "email": admin_user.email,
        "password": "testpass123",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_wrong_password(async_client: AsyncClient, admin_user: User):
    resp = await async_client.post("/api/v1/auth/login", json={
        "email": admin_user.email,
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


async def test_login_unknown_user(async_client: AsyncClient):
    resp = await async_client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "irrelevant",
    })
    assert resp.status_code == 401


async def test_get_me_no_token(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_get_me_with_token(async_client: AsyncClient, analyst_headers: dict):
    resp = await async_client.get("/api/v1/auth/me", headers=analyst_headers)
    assert resp.status_code == 200
    assert "email" in resp.json()


async def test_expired_token_rejected(async_client: AsyncClient, expired_headers: dict):
    resp = await async_client.get("/api/v1/auth/me", headers=expired_headers)
    assert resp.status_code == 401


# ── Users endpoint — admin only ───────────────────────────────────────────────

async def test_admin_can_list_users(async_client: AsyncClient, admin_headers: dict, admin_user: User):
    resp = await async_client.get("/api/v1/users", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_analyst_cannot_list_users(async_client: AsyncClient, analyst_headers: dict, analyst_user: User):
    resp = await async_client.get("/api/v1/users", headers=analyst_headers)
    assert resp.status_code == 403


async def test_viewer_cannot_list_users(async_client: AsyncClient, viewer_headers: dict, viewer_user: User):
    resp = await async_client.get("/api/v1/users", headers=viewer_headers)
    assert resp.status_code == 403


async def test_unauthenticated_cannot_list_users(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/users")
    assert resp.status_code == 401


async def test_admin_can_create_user(async_client: AsyncClient, admin_headers: dict, admin_user: User):
    resp = await async_client.post("/api/v1/users", headers=admin_headers, json={
        "email": "newuser@test.local",
        "password": "strongpassword123",
        "full_name": "New User",
        "role": "viewer",
    })
    assert resp.status_code == 201
    assert resp.json()["email"] == "newuser@test.local"


async def test_analyst_cannot_create_user(async_client: AsyncClient, analyst_headers: dict, analyst_user: User):
    resp = await async_client.post("/api/v1/users", headers=analyst_headers, json={
        "email": "hacker@test.local",
        "password": "strongpassword123",
        "full_name": "Hacker",
        "role": "admin",
    })
    assert resp.status_code == 403


async def test_viewer_cannot_create_user(async_client: AsyncClient, viewer_headers: dict, viewer_user: User):
    resp = await async_client.post("/api/v1/users", headers=viewer_headers, json={
        "email": "viewer-hack@test.local",
        "password": "strongpassword123",
        "full_name": "Viewer Hack",
        "role": "analyst",
    })
    assert resp.status_code == 403


# ── Scans — unauthenticated ───────────────────────────────────────────────────

async def test_unauthenticated_cannot_list_scans(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/scans")
    assert resp.status_code == 401


async def test_expired_token_cannot_list_scans(async_client: AsyncClient, expired_headers: dict, analyst_user: User):
    resp = await async_client.get("/api/v1/scans", headers=expired_headers)
    assert resp.status_code == 401


# ── Scans — VIEWER (read-only) ────────────────────────────────────────────────

async def test_viewer_can_list_scans(async_client: AsyncClient, viewer_headers: dict, viewer_user: User):
    resp = await async_client.get("/api/v1/scans", headers=viewer_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_viewer_cannot_create_scan(
    async_client: AsyncClient, viewer_headers: dict, viewer_user: User, target_list: TargetList,
):
    resp = await async_client.post("/api/v1/scans", headers=viewer_headers, json={
        "name": "Viewer Scan",
        "target_list_ids": [target_list.id],
        "config": {"severity": ["critical"]},
    })
    assert resp.status_code == 403


async def test_viewer_cannot_delete_scan(
    async_client: AsyncClient,
    viewer_headers: dict,
    viewer_user: User,
    test_scan: Scan,
):
    resp = await async_client.delete(f"/api/v1/scans/{test_scan.id}", headers=viewer_headers)
    assert resp.status_code == 403


# ── Scans — ANALYST ───────────────────────────────────────────────────────────

async def test_analyst_can_list_scans(async_client: AsyncClient, analyst_headers: dict, analyst_user: User):
    resp = await async_client.get("/api/v1/scans", headers=analyst_headers)
    assert resp.status_code == 200


async def test_analyst_can_read_own_scan(
    async_client: AsyncClient, analyst_headers: dict, test_scan: Scan,
):
    resp = await async_client.get(f"/api/v1/scans/{test_scan.id}", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == test_scan.id


async def test_analyst_cannot_read_other_user_scan(
    async_client: AsyncClient,
    analyst_headers: dict,
    analyst_user: User,
    admin_user: User,
    db: AsyncSession,
):
    other_scan_id = await _create_other_user_scan(db, admin_user.id)
    resp = await async_client.get(f"/api/v1/scans/{other_scan_id}", headers=analyst_headers)
    assert resp.status_code == 403


# ── Scans — ADMIN ─────────────────────────────────────────────────────────────

async def test_admin_can_list_all_scans(async_client: AsyncClient, admin_headers: dict, admin_user: User, test_scan: Scan):
    resp = await async_client.get("/api/v1/scans", headers=admin_headers)
    assert resp.status_code == 200


async def test_admin_can_read_any_scan(
    async_client: AsyncClient,
    admin_headers: dict,
    test_scan: Scan,
):
    resp = await async_client.get(f"/api/v1/scans/{test_scan.id}", headers=admin_headers)
    assert resp.status_code == 200


# ── Targets — VIEWER cannot write ─────────────────────────────────────────────

async def test_viewer_cannot_create_target(
    async_client: AsyncClient, viewer_headers: dict, viewer_user: User,
):
    resp = await async_client.post("/api/v1/targets", headers=viewer_headers, json={
        "value": "https://example.com",
        "tags": [],
    })
    assert resp.status_code == 403


async def test_viewer_cannot_create_target_list(
    async_client: AsyncClient, viewer_headers: dict, viewer_user: User,
):
    resp = await async_client.post("/api/v1/targets/lists", headers=viewer_headers, json={
        "name": "My List",
        "target_ids": [],
    })
    assert resp.status_code == 403


# ── Targets — ANALYST can write ───────────────────────────────────────────────

async def test_analyst_can_create_target(
    async_client: AsyncClient, analyst_headers: dict, analyst_user: User,
):
    resp = await async_client.post("/api/v1/targets", headers=analyst_headers, json={
        "value": "https://legit-target.com",
        "tags": ["web"],
    })
    assert resp.status_code == 201
    assert resp.json()["value"] == "https://legit-target.com"


async def test_analyst_can_create_target_list(
    async_client: AsyncClient, analyst_headers: dict, analyst_user: User,
):
    resp = await async_client.post("/api/v1/targets/lists", headers=analyst_headers, json={
        "name": "Analyst List",
        "target_ids": [],
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Analyst List"


# ── Targets — input validation through API ────────────────────────────────────

async def test_create_target_rejects_localhost_url(
    async_client: AsyncClient, analyst_headers: dict, analyst_user: User,
):
    resp = await async_client.post("/api/v1/targets", headers=analyst_headers, json={
        "value": "http://localhost/internal",
        "tags": [],
    })
    assert resp.status_code == 400


async def test_create_target_rejects_private_ip(
    async_client: AsyncClient, analyst_headers: dict, analyst_user: User,
):
    resp = await async_client.post("/api/v1/targets", headers=analyst_headers, json={
        "value": "http://192.168.1.1/admin",
        "tags": [],
    })
    assert resp.status_code == 400


async def test_create_target_rejects_javascript_protocol(
    async_client: AsyncClient, analyst_headers: dict, analyst_user: User,
):
    resp = await async_client.post("/api/v1/targets", headers=analyst_headers, json={
        "value": "javascript://alert(1)",
        "tags": [],
    })
    assert resp.status_code == 400


async def test_create_target_rejects_newline_injection(
    async_client: AsyncClient, analyst_headers: dict, analyst_user: User,
):
    resp = await async_client.post("/api/v1/targets", headers=analyst_headers, json={
        "value": "http://evil.com\nX-Injected: header",
        "tags": [],
    })
    assert resp.status_code == 400


# ── Stats endpoint ────────────────────────────────────────────────────────────

async def test_admin_can_access_stats(async_client: AsyncClient, admin_headers: dict, admin_user: User):
    resp = await async_client.get("/api/v1/scans/stats", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total_scans" in body
    assert "total_findings" in body


async def test_viewer_can_access_stats(async_client: AsyncClient, viewer_headers: dict, viewer_user: User):
    resp = await async_client.get("/api/v1/scans/stats", headers=viewer_headers)
    assert resp.status_code == 200


async def test_unauthenticated_cannot_access_stats(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/scans/stats")
    assert resp.status_code == 401


# ── Scan not found ────────────────────────────────────────────────────────────

async def test_get_nonexistent_scan_returns_404(
    async_client: AsyncClient, admin_headers: dict, admin_user: User,
):
    resp = await async_client.get(f"/api/v1/scans/{uuid.uuid4()}", headers=admin_headers)
    assert resp.status_code == 404
