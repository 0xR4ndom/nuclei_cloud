import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models.user import User, UserRole
from app.models.webhook import Webhook
from app.schemas.webhook import WebhookCreate, WebhookRead, WebhookUpdate
from app.core.rbac import can_write, owns_or_admin
from app.api.deps import get_current_user

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookRead, status_code=201)
async def create_webhook(
    payload: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    webhook = Webhook(
        id=str(uuid.uuid4()),
        name=payload.name,
        url=payload.url,
        type=payload.type,
        secret=payload.secret,
        events=payload.events,
        severity_filter=payload.severity_filter,
        is_active=payload.is_active,
        owner_id=current_user.id,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.get("", response_model=List[WebhookRead])
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Webhook)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Webhook.owner_id == current_user.id)
    result = await db.execute(query.order_by(Webhook.created_at.desc()))
    return result.scalars().all()


@router.patch("/{webhook_id}", response_model=WebhookRead)
async def update_webhook(
    webhook_id: str,
    payload: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    owns_or_admin(webhook.owner_id, current_user)

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(webhook, field, value)

    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(can_write),
):
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    owns_or_admin(webhook.owner_id, current_user)
    await db.delete(webhook)
    await db.commit()


@router.post("/{webhook_id}/test", response_model=dict)
async def test_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a test payload to the webhook URL."""
    from app.workers.notification_tasks import send_webhook_notification

    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    owns_or_admin(webhook.owner_id, current_user)

    test_payload = {
        "event": "test",
        "message": "This is a test notification from Nuclei Cloud",
        "webhook_id": webhook_id,
    }
    send_webhook_notification.delay(webhook.id, "test", test_payload)
    return {"status": "queued", "message": "Test notification dispatched"}
