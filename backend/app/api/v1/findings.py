from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional
from app.database import get_db
from app.models.user import User, UserRole
from app.models.scan import Scan
from app.models.finding import Finding, FindingSeverity
from app.schemas.finding import FindingRead, FindingListRead, FindingStats
from app.api.deps import get_current_user
import math

router = APIRouter(prefix="/findings", tags=["findings"])


async def _check_scan_access(scan_id: str, current_user: User, db: AsyncSession) -> Scan:
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if current_user.role != UserRole.ADMIN and scan.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return scan


@router.get("", response_model=FindingListRead)
async def list_findings(
    scan_id: Optional[str] = None,
    severity: Optional[FindingSeverity] = None,
    search: Optional[str] = Query(None, description="Full-text search in matched_at, template_name, description"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Finding)

    # Scope to user's scans
    if current_user.role != UserRole.ADMIN:
        user_scan_ids = (
            await db.execute(select(Scan.id).where(Scan.owner_id == current_user.id))
        ).scalars().all()
        query = query.where(Finding.scan_id.in_(user_scan_ids))

    if scan_id:
        await _check_scan_access(scan_id, current_user, db)
        query = query.where(Finding.scan_id == scan_id)

    if severity:
        query = query.where(Finding.severity == severity)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Finding.matched_at.ilike(search_term),
                Finding.template_name.ilike(search_term),
                Finding.description.ilike(search_term),
                Finding.host.ilike(search_term),
            )
        )

    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar()

    offset = (page - 1) * size
    query = query.order_by(Finding.created_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()

    return FindingListRead(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/stats", response_model=FindingStats)
async def get_finding_stats(
    scan_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(Finding)

    if current_user.role != UserRole.ADMIN:
        user_scan_ids = (
            await db.execute(select(Scan.id).where(Scan.owner_id == current_user.id))
        ).scalars().all()
        base = base.where(Finding.scan_id.in_(user_scan_ids))

    if scan_id:
        await _check_scan_access(scan_id, current_user, db)
        base = base.where(Finding.scan_id == scan_id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()

    severities = {}
    for sev in FindingSeverity:
        q = base.where(Finding.severity == sev)
        severities[sev.value] = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()

    # Top templates
    top_templates_q = (
        select(Finding.template_name, func.count().label("count"))
        .select_from(base.subquery())
        .group_by(Finding.template_name)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_templates = (await db.execute(top_templates_q)).all()

    return FindingStats(
        total=total,
        critical=severities.get("critical", 0),
        high=severities.get("high", 0),
        medium=severities.get("medium", 0),
        low=severities.get("low", 0),
        info=severities.get("info", 0),
        by_template=[{"template": r[0], "count": r[1]} for r in top_templates],
    )


@router.get("/{finding_id}", response_model=FindingRead)
async def get_finding(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    await _check_scan_access(finding.scan_id, current_user, db)
    return finding
