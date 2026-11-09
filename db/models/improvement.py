"""
SQLAlchemy 2.x Improvement Request Model
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID, UniversalJSON, TimestampMixin


if TYPE_CHECKING:
    from db.models.capability import CapabilityModel
    from db.models.pr_workflow import PRWorkflowModel
    from db.models.reflection import ReflectionModel


class ImprovementRequestModel(Base, TimestampMixin):
    __tablename__ = "improvement_requests"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    reflection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("reflections.id", ondelete="SET NULL"), index=True, nullable=True
    )
    capability_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("capabilities.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    category: Mapped[str] = mapped_column(sa.String(50), default="architecture", nullable=False)
    priority: Mapped[str] = mapped_column(sa.String(20), default="MEDIUM", nullable=False)
    status: Mapped[str] = mapped_column(sa.String(30), default="PROPOSED", index=True, nullable=False)
    proposed_changes: Mapped[Dict[str, Any]] = mapped_column(UniversalJSON, default=dict, nullable=False)

    # Relationships
    reflection: Mapped[Optional["ReflectionModel"]] = relationship(
        "ReflectionModel", back_populates="improvement_requests"
    )
    capability: Mapped[Optional["CapabilityModel"]] = relationship(
        "CapabilityModel", back_populates="improvement_requests"
    )
    pr_workflows: Mapped[List["PRWorkflowModel"]] = relationship(
        "PRWorkflowModel", back_populates="improvement_request", cascade="all, delete-orphan"
    )
