import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
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


def detect_target_type(value: str) -> TargetType:
    value = value.strip()
    if re.match(r"^https?://", value):
        return TargetType.URL
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}/\d+$", value):
        return TargetType.CIDR
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", value):
        return TargetType.IP
    return TargetType.DOMAIN


# ── Targets ──────────────────────────────────────────────────────────────────

@router.post("", response_model=TargetRead, status_code=201)
async def create_target(
    payload: TargetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    # Dedup check
    result = await db.execute(
        select(Target).where(Target.value == payload.value, Target.owner_id == current_user.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Target already exists")

    target = Target(
        id=str(uuid.uuid4()),
        value=payload.value.strip(),
        type=payload.type,
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
    """Bulk import targets with auto-detection and deduplication."""
    created = 0
    skipped = 0
    target_ids = []

    for raw in payload.targets:
        value = raw.strip()
        if not value:
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

    # Optionally add to a target list
    if payload.target_list_id and target_ids:
        tl_result = await db.execute(
            select(TargetList).where(TargetList.id == payload.target_list_id)
        )
        tl = tl_result.scalar_one_or_none()
        if tl:
            owns_or_admin(tl.owner_id, current_user)
            for tid in target_ids:
                await db.execute(
                    target_list_targets.insert().prefix_with("OR IGNORE").values(
                        target_list_id=payload.target_list_id, target_id=tid
                    )
                )

    await db.commit()
    return {"created": created, "skipped": skipped, "total": len(target_ids)}


@router.post("/upload", response_model=dict)
async def upload_targets(
    file: UploadFile = File(...),
    target_list_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    """Upload a text file with one target per line."""
    content = await file.read()
    lines = content.decode("utf-8").splitlines()
    raw_targets = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
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
