import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import enum


class TemplateSource(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    CUSTOM = "CUSTOM"


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    reference: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[TemplateSource] = mapped_column(SAEnum(TemplateSource), default=TemplateSource.OFFICIAL, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
