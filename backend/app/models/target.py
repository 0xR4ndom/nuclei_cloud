import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Table, Column, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class TargetType(str, enum.Enum):
    URL = "URL"
    IP = "IP"
    CIDR = "CIDR"
    DOMAIN = "DOMAIN"


target_list_targets = Table(
    "target_list_targets",
    Base.metadata,
    Column("target_list_id", String, ForeignKey("target_lists.id"), primary_key=True),
    Column("target_id", String, ForeignKey("targets.id"), primary_key=True),
)


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    value: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    type: Mapped[TargetType] = mapped_column(SAEnum(TargetType), nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    lists = relationship("TargetList", secondary=target_list_targets, back_populates="targets")


class TargetList(Base):
    __tablename__ = "target_lists"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=True)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    targets = relationship("Target", secondary=target_list_targets, back_populates="lists")
    owner = relationship("User", back_populates="target_lists")
