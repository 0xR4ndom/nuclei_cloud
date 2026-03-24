import uuid
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from app.database import get_db
from app.models.user import User, UserRole
from app.models.scan import Scan, ScanStatus, ScanTargetList
from app.models.finding import Finding
from app.schemas.scan import ScanCreate, ScanRead, ScanListRead, ScanUpdate
from app.core.rbac import can_write, owns_or_admin
from app.api.deps import get_current_user

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("", response_model=ScanRead, status_code=201)
async def create_scan(
    payload: ScanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    from app.workers.scan_tasks import run_nuclei_scan

    scan = Scan(
        id=str(uuid.uuid4()),
        name=payload.name,
        status=ScanStatus.PENDING,
        owner_id=current_user.id,
        config=payload.config.model_dump(),
        scheduled_at=payload.scheduled_at,
    )
    db.add(scan)
    await db.flush()

    for list_id in payload.target_list_ids:
        db.add(ScanTargetList(scan_id=scan.id, target_list_id=list_id))

    await db.commit()
    await db.refresh(scan)

    # Dispatch to Celery
    if payload.scheduled_at and payload.scheduled_at > datetime.utcnow():
        eta = payload.scheduled_at
        task = run_nuclei_scan.apply_async(args=[scan.id], eta=eta)
    else:
        task = run_nuclei_scan.delay(scan.id)

    scan.celery_task_id = task.id
    scan.status = ScanStatus.QUEUED
    await db.commit()
    await db.refresh(scan)
    return scan


@router.get("", response_model=List[ScanListRead])
async def list_scans(
    status: Optional[ScanStatus] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Scan)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Scan.owner_id == current_user.id)
    if status:
        query = query.where(Scan.status == status)
    query = query.order_by(Scan.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats", response_model=dict)
async def get_global_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate stats for the dashboard."""
    from app.models.finding import FindingSeverity

    base_scan = select(Scan)
    base_finding = select(Finding)

    if current_user.role != UserRole.ADMIN:
        scan_ids_q = select(Scan.id).where(Scan.owner_id == current_user.id)
        scan_ids = (await db.execute(scan_ids_q)).scalars().all()
        base_finding = base_finding.where(Finding.scan_id.in_(scan_ids))
        base_scan = base_scan.where(Scan.owner_id == current_user.id)

    total_scans = (await db.execute(select(func.count()).select_from(base_scan.subquery()))).scalar()
    total_findings = (await db.execute(select(func.count()).select_from(base_finding.subquery()))).scalar()

    severities = {}
    for sev in FindingSeverity:
        q = base_finding.where(Finding.severity == sev)
        count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
        severities[sev.value] = count

    running = (await db.execute(
        select(func.count()).select_from(
            base_scan.where(Scan.status == ScanStatus.RUNNING).subquery()
        )
    )).scalar()

    return {
        "total_scans": total_scans,
        "total_findings": total_findings,
        "running_scans": running,
        "findings_by_severity": severities,
    }


@router.get("/{scan_id}", response_model=ScanRead)
async def get_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if current_user.role != UserRole.ADMIN and scan.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return scan


@router.post("/{scan_id}/cancel", response_model=ScanRead)
async def cancel_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    from celery.app.control import Inspect
    from app.workers.celery_app import celery_app

    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    owns_or_admin(scan.owner_id, current_user)

    if scan.status not in (ScanStatus.PENDING, ScanStatus.QUEUED, ScanStatus.RUNNING):
        raise HTTPException(status_code=400, detail="Scan cannot be cancelled in its current state")

    if scan.celery_task_id:
        celery_app.control.revoke(scan.celery_task_id, terminate=True, signal="SIGTERM")

    scan.status = ScanStatus.CANCELLED
    await db.commit()
    await db.refresh(scan)
    return scan


@router.delete("/{scan_id}", status_code=204)
async def delete_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    owns_or_admin(scan.owner_id, current_user)
    await db.delete(scan)
    await db.commit()


@router.get("/{scan_id}/stream")
async def stream_scan_events(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Server-Sent Events stream for real-time scan updates."""
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if current_user.role != UserRole.ADMIN and scan.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    async def event_generator():
        last_finding_count = 0
        while True:
            result = await db.execute(select(Scan).where(Scan.id == scan_id))
            scan = result.scalar_one_or_none()
            if not scan:
                break

            findings_q = await db.execute(
                select(Finding)
                .where(Finding.scan_id == scan_id)
                .order_by(Finding.created_at.desc())
                .limit(10)
                .offset(last_finding_count)
            )
            new_findings = findings_q.scalars().all()

            event_data = {
                "status": scan.status.value,
                "total_findings": scan.total_findings,
                "critical": scan.critical_count,
                "high": scan.high_count,
                "new_findings": [
                    {
                        "id": f.id,
                        "template_name": f.template_name,
                        "severity": f.severity.value,
                        "matched_at": f.matched_at,
                    }
                    for f in new_findings
                ],
            }
            last_finding_count += len(new_findings)
            yield f"data: {json.dumps(event_data)}\n\n"

            if scan.status in (ScanStatus.DONE, ScanStatus.FAILED, ScanStatus.CANCELLED):
                yield "data: {\"done\": true}\n\n"
                break

            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
