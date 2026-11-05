"""
SQLAlchemy 2.x Audit Event Model
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base, GUID, UniversalJSON


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(sa.String(100), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(sa.String(100), default="system", index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(sa.String(50), index=True, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(UniversalJSON, default=dict, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
        nullable=False,
    )
