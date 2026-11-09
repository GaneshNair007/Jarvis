"""
SQLAlchemy 2.x Safe PR Workflow Model
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base, GUID, TimestampMixin


if TYPE_CHECKING:
    from db.models.improvement import ImprovementRequestModel


class PRWorkflowModel(Base, TimestampMixin):
    __tablename__ = "pr_workflows"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    improvement_request_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("improvement_requests.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    target_branch: Mapped[str] = mapped_column(sa.String(100), default="main", nullable=False)
    pr_number: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    pr_url: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    workflow_state: Mapped[str] = mapped_column(sa.String(30), default="PROPOSED", index=True, nullable=False)
    security_passed: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    tests_passed: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    # Relationships
    improvement_request: Mapped["ImprovementRequestModel"] = relationship(
        "ImprovementRequestModel", back_populates="pr_workflows"
    )
