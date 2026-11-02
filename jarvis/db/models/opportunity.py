"""
SQLAlchemy 2.x Opportunity Model for JARVIS
Opportunity Engine table for high-value hackathons, internships, jobs, and research programs.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from jarvis.db.models.base import Base, GUID, UniversalJSON


class OpportunityModel(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    opportunity_type: Mapped[str] = mapped_column("type", sa.String(50), index=True, nullable=False)
    source: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    score: Mapped[float] = mapped_column(sa.Float, default=0.0, index=True, nullable=False)
    justification: Mapped[str] = mapped_column(sa.Text, default="", nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)
    discovered_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
        nullable=False,
    )

