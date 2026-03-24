import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, JSON, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class FindingSeverity(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id: Mapped[str] = mapped_column(String, ForeignKey("scans.id"), nullable=False, index=True)

    # Template info
    template_id: Mapped[str] = mapped_column(String(512), nullable=True)
    template_name: Mapped[str] = mapped_column(String(512), nullable=True)
    template_path: Mapped[str] = mapped_column(String(1024), nullable=True)

    # Finding details
    severity: Mapped[FindingSeverity] = mapped_column(SAEnum(FindingSeverity), nullable=False, index=True)
    matched_at: Mapped[str] = mapped_column(String(2048), nullable=False)
    target: Mapped[str] = mapped_column(String(2048), nullable=False)
    host: Mapped[str] = mapped_column(String(1024), nullable=True)
    matched_line: Mapped[str] = mapped_column(Text, nullable=True)
    extracted_results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    curl_command: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    reference: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Full raw JSON from nuclei output
    raw: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    scan = relationship("Scan", back_populates="findings")

    __table_args__ = (
        Index("ix_findings_scan_severity", "scan_id", "severity"),
    )
