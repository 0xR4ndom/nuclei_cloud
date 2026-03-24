import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, JSON, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class WebhookType(str, enum.Enum):
    DISCORD = "DISCORD"
    SLACK = "SLACK"
    JIRA = "JIRA"
    GENERIC = "GENERIC"


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    type: Mapped[WebhookType] = mapped_column(SAEnum(WebhookType), default=WebhookType.GENERIC, nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=True)
    events: Mapped[list] = mapped_column(JSON, default=lambda: ["scan.completed", "finding.critical"], nullable=False)
    # e.g. ["scan.completed", "scan.failed", "finding.critical", "finding.high"]
    severity_filter: Mapped[list] = mapped_column(JSON, default=lambda: ["critical", "high"], nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="webhooks")
