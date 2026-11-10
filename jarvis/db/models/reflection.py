"""
SQLAlchemy 2.x Reflection Model for JARVIS
Stores post-goal retrospectives, successes, failures, lessons, and self-improvement loops.
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.models.base import Base, GUID, UniversalJSON

if TYPE_CHECKING:
    from jarvis.db.models.goal import GoalModel


class ReflectionModel(Base):
    __tablename__ = "reflections"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False)
    successes: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)
    failures: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)
    improvements: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)
    opportunities: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)
    metrics: Mapped[Dict[str, Any]] = mapped_column(UniversalJSON, default=dict, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationships
    goal: Mapped["GoalModel"] = relationship("GoalModel", back_populates="reflections")

