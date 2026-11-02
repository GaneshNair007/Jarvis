"""
SQLAlchemy 2.x Department Model
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID, UniversalJSON, TimestampMixin


class DepartmentModel(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    dept_key: Mapped[str] = mapped_column(sa.String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    manager_agent: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, default="", nullable=False)
    capabilities: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)

    # Relationships
    agents: Mapped[List["AgentModel"]] = relationship(
        "AgentModel", back_populates="department", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["AssignmentModel"]] = relationship(
        "AssignmentModel", back_populates="department"
    )
