"""
SQLAlchemy 2.x Agent Lifecycle Model for JARVIS
Enables dynamic agent lifecycle management (created, paused, resumed, retired)
so JARVIS dynamically spawns worker agents on-demand instead of keeping 100+ idle processes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import datetime
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.models.base import Base, GUID


if TYPE_CHECKING:
    from jarvis.db.models.agent import AgentModel


class AgentLifecycleModel(Base):
    __tablename__ = "agent_lifecycle"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    state: Mapped[str] = mapped_column(sa.String(50), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text, default="", nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
        nullable=False,
    )

    # Relationships
    agent: Mapped["AgentModel"] = relationship("AgentModel", back_populates="lifecycles")
