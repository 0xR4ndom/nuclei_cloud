from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.target import TargetType


class TargetCreate(BaseModel):
    value: str
    type: TargetType
    tags: List[str] = []


class TargetRead(BaseModel):
    id: str
    value: str
    type: TargetType
    tags: List[str]
    owner_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TargetImport(BaseModel):
    targets: List[str]  # raw list, auto-detect type
    tags: List[str] = []
    target_list_id: Optional[str] = None


class TargetListCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_ids: List[str] = []


class TargetListRead(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    target_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TargetListDetail(TargetListRead):
    targets: List[TargetRead] = []
