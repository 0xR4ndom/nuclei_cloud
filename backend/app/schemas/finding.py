from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.finding import FindingSeverity


class FindingRead(BaseModel):
    id: str
    scan_id: str
    template_id: Optional[str]
    template_name: Optional[str]
    severity: FindingSeverity
    matched_at: str
    target: str
    host: Optional[str]
    description: Optional[str]
    matched_line: Optional[str]
    extracted_results: List[str]
    curl_command: Optional[str]
    reference: List[str]
    tags: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class FindingListRead(BaseModel):
    items: List[FindingRead]
    total: int
    page: int
    size: int
    pages: int


class FindingStats(BaseModel):
    total: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    by_template: List[Dict[str, Any]] = []
    by_target: List[Dict[str, Any]] = []
