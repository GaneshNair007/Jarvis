"""
SQLAlchemy 2.x Execution Run Model
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID, UniversalJSON


if TYPE_CHECKING:
    from db.models.agent import AgentModel
    from db.models.task import TaskModel


class ExecutionModel(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("agents.id", ondelete="SET NULL"), index=True, nullable=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(sa.String(20), default="RUNNING", index=True, nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    logs: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    outputs: Mapped[Dict[str, Any]] = mapped_column(UniversalJSON, default=dict, nullable=False)
    verification_score: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    verification_passed: Mapped[Optional[bool]] = mapped_column(sa.Boolean, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationships
    task: Mapped["TaskModel"] = relationship("TaskModel", back_populates="executions")
    agent: Mapped[Optional["AgentModel"]] = relationship("AgentModel", back_populates="executions")
