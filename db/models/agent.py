"""
SQLAlchemy 2.x Agent Model
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID, UniversalJSON, TimestampMixin


class AgentModel(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    agent_key: Mapped[str] = mapped_column(sa.String(100), unique=True, index=True, nullable=False)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    role: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), default="ACTIVE", index=True, nullable=False)
    capabilities: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)

    # Relationships
    department: Mapped[Optional["DepartmentModel"]] = relationship("DepartmentModel", back_populates="agents")
    assignments: Mapped[List["AssignmentModel"]] = relationship("AssignmentModel", back_populates="agent", cascade="all, delete-orphan")
    executions: Mapped[List["ExecutionModel"]] = relationship("ExecutionModel", back_populates="agent")
