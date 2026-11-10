"""
SQLAlchemy 2.x Agent Assignment Model for JARVIS
Tracks cryptographic dispatch and delegation records between tasks and agents.
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.models.base import Base, GUID

if TYPE_CHECKING:
    from jarvis.db.models.agent import AgentModel
    from jarvis.db.models.task import TaskModel


class AssignmentModel(Base):
    __tablename__ = "agent_assignments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    assigned_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    # Relationships
    agent: Mapped["AgentModel"] = relationship("AgentModel", back_populates="assignments")
    task: Mapped["TaskModel"] = relationship("TaskModel", back_populates="assignments")

