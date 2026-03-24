"""
Webhook notification tasks.
Supports Discord, Slack, Jira, and generic HTTP webhooks.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.config import settings
from app.models.scan import Scan
from app.models.webhook import Webhook, WebhookType
from app.models.finding import Finding, FindingSeverity

logger = logging.getLogger(__name__)

_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


def _get_session() -> Session:
    return Session(_engine)


SEVERITY_COLORS = {
    "critical": 0xFF0000,   # red
    "high": 0xFF6600,       # orange
    "medium": 0xFFCC00,     # yellow
    "low": 0x00CCFF,        # blue
    "info": 0x808080,       # grey
}


def _build_discord_payload(event: str, data: dict) -> dict:
    scan_name = data.get("scan_name", "Unknown Scan")
    total = data.get("total_findings", 0)
    critical = data.get("critical", 0)
    high = data.get("high", 0)
    status = data.get("status", "")

    color = 0x00FF00 if status == "DONE" else 0xFF0000
    if critical > 0:
        color = SEVERITY_COLORS["critical"]
    elif high > 0:
        color = SEVERITY_COLORS["high"]

    embed = {
        "title": f"🔍 Nuclei Scan: {scan_name}",
        "color": color,
        "fields": [
            {"name": "Status", "value": status, "inline": True},
            {"name": "Total Findings", "value": str(total), "inline": True},
            {"name": "Critical", "value": str(critical), "inline": True},
            {"name": "High", "value": str(high), "inline": True},
            {"name": "Medium", "value": str(data.get("medium", 0)), "inline": True},
            {"name": "Low", "value": str(data.get("low", 0)), "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Nuclei Cloud"},
    }
    return {"embeds": [embed]}


def _build_slack_payload(event: str, data: dict) -> dict:
    scan_name = data.get("scan_name", "Unknown Scan")
    status = data.get("status", "")
    total = data.get("total_findings", 0)
    critical = data.get("critical", 0)
    high = data.get("high", 0)

    color = "good" if status == "DONE" and critical == 0 else "danger"

    return {
        "attachments": [
            {
                "color": color,
                "title": f"Nuclei Scan: {scan_name}",
                "fields": [
                    {"title": "Status", "value": status, "short": True},
                    {"title": "Total Findings", "value": str(total), "short": True},
                    {"title": "Critical", "value": str(critical), "short": True},
                    {"title": "High", "value": str(high), "short": True},
                ],
                "footer": "Nuclei Cloud",
                "ts": int(datetime.utcnow().timestamp()),
            }
        ]
    }


def _sign_payload(secret: str, payload_bytes: bytes) -> str:
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def _send_http(webhook: Webhook, event: str, data: dict) -> bool:
    payload_bytes = json.dumps(data).encode()
    headers = {"Content-Type": "application/json", "X-Nuclei-Event": event}

    if webhook.secret:
        sig = hmac.new(webhook.secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        headers["X-Nuclei-Signature"] = f"sha256={sig}"

    if webhook.type == WebhookType.DISCORD:
        body = _build_discord_payload(event, data)
    elif webhook.type == WebhookType.SLACK:
        body = _build_slack_payload(event, data)
    else:
        body = {"event": event, "data": data}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(webhook.url, json=body, headers=headers)
            resp.raise_for_status()
            return True
    except httpx.HTTPError as e:
        logger.error(f"Webhook {webhook.id} failed: {e}")
        return False


@celery_app.task(name="app.workers.notification_tasks.notify_scan_completed",
                 max_retries=3, default_retry_delay=30)
def notify_scan_completed(scan_id: str):
    """Send notifications to all matching webhooks after a scan completes."""
    with _get_session() as session:
        scan = session.get(Scan, scan_id)
        if not scan:
            return

        data = {
            "scan_id": scan_id,
            "scan_name": scan.name,
            "status": scan.status.value,
            "total_findings": scan.total_findings,
            "critical": scan.critical_count,
            "high": scan.high_count,
            "medium": scan.medium_count,
            "low": scan.low_count,
            "info": scan.info_count,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        }

        event = "scan.completed" if scan.status.value == "DONE" else "scan.failed"

        # Find webhooks for this owner that match the event
        result = session.execute(
            select(Webhook).where(
                Webhook.owner_id == scan.owner_id,
                Webhook.is_active == True,
            )
        )
        webhooks = result.scalars().all()

        for webhook in webhooks:
            if event in webhook.events:
                _send_http(webhook, event, data)


@celery_app.task(name="app.workers.notification_tasks.send_webhook_notification",
                 max_retries=3, default_retry_delay=30)
def send_webhook_notification(webhook_id: str, event: str, data: dict):
    """Send a specific notification to a single webhook."""
    with _get_session() as session:
        webhook = session.get(Webhook, webhook_id)
        if not webhook or not webhook.is_active:
            return
        _send_http(webhook, event, data)
