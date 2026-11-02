"""
SQLAlchemy 2.x Department Model for JARVIS
Defines organizational boundaries and management divisions.
"""

from __future__ import annotations

import uuid
from typing import List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.models.base import Base, GUID, UniversalJSON, TimestampMixin


class DepartmentModel(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(100), unique=True, index=True, nullable=False)
    manager_agent: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, default="", nullable=False)
    capabilities: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)

    # Relationships
    agents: Mapped[List["AgentModel"]] = relationship(
        "AgentModel", back_populates="department", cascade="all, delete-orphan"
    )
