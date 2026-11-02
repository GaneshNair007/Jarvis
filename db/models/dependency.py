"""
SQLAlchemy 2.x Task Dependency Model
"""

from __future__ import annotations

import datetime
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID


class TaskDependencyModel(Base):
    __tablename__ = "task_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationships
    task: Mapped["TaskModel"] = relationship(
        "TaskModel",
        foreign_keys=[task_id],
        back_populates="dependencies",
    )
    depends_on_task: Mapped["TaskModel"] = relationship(
        "TaskModel",
        foreign_keys=[depends_on_task_id],
        back_populates="dependents",
    )
