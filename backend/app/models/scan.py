import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, JSON, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class ScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ScanSeverityFilter(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(SAEnum(ScanStatus), default=ScanStatus.PENDING, nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=True)

    # Nuclei config stored as JSON
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # e.g. {"severity": ["critical","high"], "tags": ["cve"], "templates": [...], "rate_limit": 150}

    # Stats
    total_targets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    info_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="scans")
    findings = relationship("Finding", back_populates="scan", lazy="select", cascade="all, delete-orphan")
    target_lists = relationship("ScanTargetList", back_populates="scan", cascade="all, delete-orphan")


class ScanTargetList(Base):
    __tablename__ = "scan_target_lists"

    scan_id: Mapped[str] = mapped_column(String, ForeignKey("scans.id"), primary_key=True)
    target_list_id: Mapped[str] = mapped_column(String, ForeignKey("target_lists.id"), primary_key=True)

    scan = relationship("Scan", back_populates="target_lists")
    target_list = relationship("TargetList")
