from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime
from app.models.webhook import WebhookType


class WebhookCreate(BaseModel):
    name: str
    url: str
    type: WebhookType = WebhookType.GENERIC
    secret: Optional[str] = None
    events: List[str] = ["scan.completed", "finding.critical"]
    severity_filter: List[str] = ["critical", "high"]
    is_active: bool = True


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    severity_filter: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookRead(BaseModel):
    id: str
    name: str
    url: str
    type: WebhookType
    events: List[str]
    severity_filter: List[str]
    is_active: bool
    owner_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
