import re
import uuid
import ipaddress
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import List, Optional
from app.database import get_db
from app.models.user import User, UserRole
from app.models.target import Target, TargetList, TargetType, target_list_targets
from app.schemas.target import (
    TargetCreate, TargetRead, TargetListCreate, TargetListRead,
    TargetListDetail, TargetImport,
)
from app.core.rbac import can_write, owns_or_admin
from app.api.deps import get_current_user

router = APIRouter(prefix="/targets", tags=["targets"])

# Protocols that must never be scanned (SSRF / injection risks)
_BLOCKED_PROTOCOLS = re.compile(
    r"^(javascript|data|file|ftp|ldap|ldaps|gopher|dict|tftp|sftp|mailto)://",
    re.IGNORECASE,
)
# Block control characters, newlines, null bytes in any target value
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# Private / loopback / link-local ranges — not allowed as scan targets
_SSRF_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),   # AWS/Azure metadata
    ipaddress.ip_network("100.64.0.0/10"),    # Shared address space
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 ULA
]


def _is_ssrf_ip(addr_str: str) -> bool:
    """Return True if the address belongs to a private/loopback/SSRF-risk range."""
    try:
        addr = ipaddress.ip_address(addr_str)
        return any(addr in net for net in _SSRF_NETWORKS)
    except ValueError:
        return False


def _validate_target_value(value: str) -> str:
    """
    Sanitise and validate a raw target string.
    Raises HTTPException 400 on any dangerous input.
    Returns the cleaned value.
    """
    value = value.strip()
    if not value:
        raise HTTPException(status_code=400, detail="Target value cannot be empty")

    if len(value) > 2048:
        raise HTTPException(status_code=400, detail="Target value exceeds 2048 characters")

    # Reject control characters (newlines, null bytes — CLI injection surface)
    if _CONTROL_CHARS.search(value):
        raise HTTPException(
            status_code=400,
            detail="Target value contains illegal control characters",
        )

    # Reject dangerous protocols
    if _BLOCKED_PROTOCOLS.match(value):
        raise HTTPException(
            status_code=400,
            detail="Blocked protocol. Only http://, https://, IPs, CIDRs, and domains are allowed",
        )

    # Protocol-specific validation
    if re.match(r"^https?://", value, re.IGNORECASE):
        # Block SSRF via hostname
        host_match = re.match(r"^https?://([^/:?\s#]+)", value, re.IGNORECASE)
        if host_match:
            host = host_match.group(1)
            # Block localhost
            if host.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                raise HTTPException(status_code=400, detail="Scanning localhost is not allowed")
            # Block link-local / metadata endpoints
            if _is_ssrf_ip(host):
                raise HTTPException(
                    status_code=400,
                    detail="Scanning private/loopback/metadata IP ranges is not allowed",
                )
        return value

    # Validate CIDR
    if re.match(r"^[\d.]+/\d+$", value) or re.match(r"^[0-9a-fA-F:]+/\d+$", value):
        try:
            net = ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid CIDR notation: {value}")
        if any(net.overlaps(blocked) for blocked in _SSRF_NETWORKS):
            raise HTTPException(status_code=400, detail="CIDR overlaps with private/SSRF-risk ranges")
        return value

    # Validate plain IP
    if re.match(r"^[\d.]+$", value) or re.match(r"^[0-9a-fA-F:]+$", value):
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IP address: {value}")
        if _is_ssrf_ip(value):
            raise HTTPException(status_code=400, detail="Scanning private/SSRF-risk IPs is not allowed")
        return value

    # Domain: basic sanity check
    if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,251}[a-zA-Z0-9])?$", value):
        raise HTTPException(status_code=400, detail=f"Invalid domain format: {value}")

    if value.lower() in ("localhost",):
        raise HTTPException(status_code=400, detail="Scanning localhost is not allowed")

    return value


def detect_target_type(value: str) -> TargetType:
    """Detect target type AFTER validation (value is already sanitised)."""
    if re.match(r"^https?://", value, re.IGNORECASE):
        return TargetType.URL
    try:
        if "/" in value:
            ipaddress.ip_network(value, strict=False)
            return TargetType.CIDR
        ipaddress.ip_address(value)
        return TargetType.IP
    except ValueError:
        pass
    return TargetType.DOMAIN


# ── Targets ───────────────────────────────────────────────────────────────────

@router.post("", response_model=TargetRead, status_code=201)
async def create_target(
    payload: TargetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    clean_value = _validate_target_value(payload.value)

    # Dedup check
    result = await db.execute(
        select(Target).where(Target.value == clean_value, Target.owner_id == current_user.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Target already exists")

    target = Target(
        id=str(uuid.uuid4()),
        value=clean_value,
        type=detect_target_type(clean_value),
        tags=payload.tags,
        owner_id=current_user.id,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target


@router.post("/import", response_model=dict)
async def import_targets(
    payload: TargetImport,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    """Bulk import targets with auto-detection, validation, and deduplication."""
    from app.config import settings

    if len(payload.targets) > settings.MAX_TARGETS_PER_SCAN:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot import more than {settings.MAX_TARGETS_PER_SCAN} targets at once",
        )

    created = 0
    skipped = 0
    rejected = 0
    target_ids = []

    for raw in payload.targets:
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue

        # Validate — skip invalid entries with a count rather than failing the whole batch
        try:
            value = _validate_target_value(raw)
        except HTTPException:
            rejected += 1
            continue

        result = await db.execute(
            select(Target).where(Target.value == value, Target.owner_id == current_user.id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            skipped += 1
            target_ids.append(existing.id)
        else:
            target = Target(
                id=str(uuid.uuid4()),
                value=value,
                type=detect_target_type(value),
                tags=payload.tags,
                owner_id=current_user.id,
            )
            db.add(target)
            created += 1
            target_ids.append(target.id)

    # Flush new targets so we can reference their IDs
    await db.flush()

    # Optionally add to a target list (PostgreSQL ON CONFLICT DO NOTHING)
    if payload.target_list_id and target_ids:
        tl_result = await db.execute(
            select(TargetList).where(TargetList.id == payload.target_list_id)
        )
        tl = tl_result.scalar_one_or_none()
        if tl:
            owns_or_admin(tl.owner_id, current_user)
            stmt = (
                pg_insert(target_list_targets)
                .values([
                    {"target_list_id": payload.target_list_id, "target_id": tid}
                    for tid in target_ids
                ])
                .on_conflict_do_nothing()
            )
            await db.execute(stmt)

    await db.commit()
    return {
        "created": created,
        "skipped": skipped,
        "rejected": rejected,
        "total": len(target_ids),
    }


@router.post("/upload", response_model=dict)
async def upload_targets(
    file: UploadFile = File(...),
    target_list_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    """Upload a text file (max 10 MB) with one target per line."""
    MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8")

    lines = text.splitlines()
    raw_targets = [
        line.strip() for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    payload = TargetImport(targets=raw_targets, target_list_id=target_list_id)
    return await import_targets(payload, db, current_user, current_user)


@router.get("", response_model=List[TargetRead])
async def list_targets(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Target)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Target.owner_id == current_user.id)
    query = query.offset(skip).limit(limit).order_by(Target.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/{target_id}", status_code=204)
async def delete_target(
    target_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    result = await db.execute(select(Target).where(Target.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    owns_or_admin(target.owner_id, current_user)
    await db.delete(target)
    await db.commit()


# ── Target Lists ──────────────────────────────────────────────────────────────

@router.post("/lists", response_model=TargetListRead, status_code=201)
async def create_target_list(
    payload: TargetListCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    tl = TargetList(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
    )
    db.add(tl)
    await db.flush()

    for tid in payload.target_ids:
        t_result = await db.execute(select(Target).where(Target.id == tid))
        t = t_result.scalar_one_or_none()
        if t:
            tl.targets.append(t)

    await db.commit()
    await db.refresh(tl)
    count = len(tl.targets)
    data = TargetListRead(
        id=tl.id, name=tl.name, description=tl.description,
        owner_id=tl.owner_id, target_count=count,
        created_at=tl.created_at, updated_at=tl.updated_at,
    )
    return data


@router.get("/lists", response_model=List[TargetListRead])
async def list_target_lists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(TargetList)
    if current_user.role != UserRole.ADMIN:
        query = query.where(TargetList.owner_id == current_user.id)
    result = await db.execute(query.order_by(TargetList.created_at.desc()))
    lists = result.scalars().all()
    out = []
    for tl in lists:
        count = len(tl.targets) if tl.targets else 0
        out.append(TargetListRead(
            id=tl.id, name=tl.name, description=tl.description,
            owner_id=tl.owner_id, target_count=count,
            created_at=tl.created_at, updated_at=tl.updated_at,
        ))
    return out


@router.get("/lists/{list_id}", response_model=TargetListDetail)
async def get_target_list(
    list_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(TargetList).where(TargetList.id == list_id))
    tl = result.scalar_one_or_none()
    if not tl:
        raise HTTPException(status_code=404, detail="Target list not found")
    owns_or_admin(tl.owner_id, current_user)

    targets = [TargetRead.model_validate(t) for t in tl.targets]
    return TargetListDetail(
        id=tl.id, name=tl.name, description=tl.description,
        owner_id=tl.owner_id, target_count=len(targets),
        created_at=tl.created_at, updated_at=tl.updated_at,
        targets=targets,
    )


@router.delete("/lists/{list_id}", status_code=204)
async def delete_target_list(
    list_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    result = await db.execute(select(TargetList).where(TargetList.id == list_id))
    tl = result.scalar_one_or_none()
    if not tl:
        raise HTTPException(status_code=404, detail="Target list not found")
    owns_or_admin(tl.owner_id, current_user)
    await db.delete(tl)
    await db.commit()
