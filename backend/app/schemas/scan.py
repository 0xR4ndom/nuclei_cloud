from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.scan import ScanStatus


class ScanConfig(BaseModel):
    severity: List[str] = ["critical", "high", "medium"]
    tags: List[str] = []
    templates: List[str] = []  # specific template paths
    exclude_tags: List[str] = []
    rate_limit: int = 150
    bulk_size: int = 25
    concurrency: int = 25
    timeout: int = 30
    retries: int = 1
    extra_flags: List[str] = []


class ScanCreate(BaseModel):
    name: str
    target_list_ids: List[str]
    config: ScanConfig = ScanConfig()
    scheduled_at: Optional[datetime] = None


class ScanUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[ScanStatus] = None


class ScanListRead(BaseModel):
    id: str
    name: str
    status: ScanStatus
    owner_id: str
    total_targets: int
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    scheduled_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ScanRead(ScanListRead):
    config: Dict[str, Any]
    celery_task_id: Optional[str]
    error_message: Optional[str]
    updated_at: datetime
