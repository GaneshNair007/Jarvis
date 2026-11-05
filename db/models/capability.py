"""
SQLAlchemy 2.x Capability Model
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID, UniversalJSON, TimestampMixin


class CapabilityModel(Base, TimestampMixin):
    __tablename__ = "capabilities"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(100), unique=True, index=True, nullable=False)
    level: Mapped[str] = mapped_column(sa.String(30), default="EXPERIMENTAL", index=True, nullable=False)
    category: Mapped[str] = mapped_column(sa.String(50), default="general", index=True, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, default="", nullable=False)
    required_tools: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)
    success_rate: Mapped[float] = mapped_column(sa.Float, default=1.0, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)

    # Relationships
    improvement_requests: Mapped[List["ImprovementRequestModel"]] = relationship(
        "ImprovementRequestModel", back_populates="capability"
    )
