"""
SQLAlchemy 2.x Assignment Model
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID, UniversalJSON


class AssignmentModel(Base):
    __tablename__ = "assignments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID, sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), default="ASSIGNED", index=True, nullable=False)
    assigned_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)

    # Relationships
    task: Mapped["TaskModel"] = relationship("TaskModel", back_populates="assignments")
    agent: Mapped["AgentModel"] = relationship("AgentModel", back_populates="assignments")
    department: Mapped[Optional["DepartmentModel"]] = relationship("DepartmentModel", back_populates="assignments")
