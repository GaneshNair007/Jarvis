"""
SQLAlchemy 2.x Memory Model
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID, UniversalJSON, TimestampMixin


if TYPE_CHECKING:
    from db.models.goal import GoalModel


class MemoryModel(Base, TimestampMixin):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    source_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("tasks.id", ondelete="SET NULL"), index=True, nullable=True
    )
    goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("goals.id", ondelete="SET NULL"), index=True, nullable=True
    )
    category: Mapped[str] = mapped_column(sa.String(50), index=True, nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column(UniversalJSON, nullable=False)
    importance_score: Mapped[float] = mapped_column(sa.Float, default=1.0, nullable=False)
    access_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)

    # Relationships
    goal: Mapped[Optional["GoalModel"]] = relationship("GoalModel", back_populates="memories")
