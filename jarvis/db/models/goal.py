"""
SQLAlchemy 2.x Goal Model for JARVIS
Highest-level strategic objective in the operational brain hierarchy.
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.models.base import Base, GUID, UniversalJSON, TimestampMixin


if TYPE_CHECKING:
    from jarvis.db.models.memory import MemoryModel
    from jarvis.db.models.reflection import ReflectionModel
    from jarvis.db.models.task import TaskGraphModel, TaskModel


class GoalModel(Base, TimestampMixin):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(sa.String(100), default="ganesh", nullable=False)
    priority: Mapped[str] = mapped_column(sa.String(20), default="HIGH", index=True, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), default="PENDING", index=True, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)

    # Relationships
    task_graphs: Mapped[List["TaskGraphModel"]] = relationship(
        "TaskGraphModel", back_populates="goal", cascade="all, delete-orphan"
    )
    tasks: Mapped[List["TaskModel"]] = relationship("TaskModel", back_populates="goal", cascade="all, delete-orphan")
    reflections: Mapped[List["ReflectionModel"]] = relationship(
        "ReflectionModel", back_populates="goal", cascade="all, delete-orphan"
    )
    memories: Mapped[List["MemoryModel"]] = relationship("MemoryModel", back_populates="goal")
