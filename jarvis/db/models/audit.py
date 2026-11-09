"""
SQLAlchemy 2.x Audit Trail Model for JARVIS
Immutable audit log recording every important action, actor, target, and payload.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from jarvis.db.models.base import Base, GUID, UniversalJSON


class AuditModel(Base):
    __tablename__ = "audits"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(sa.String(100), default="system", index=True, nullable=False)
    action: Mapped[str] = mapped_column(sa.String(100), index=True, nullable=False)
    target: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
        nullable=False,
    )
