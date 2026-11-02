"""
SQLAlchemy 2.x Schedule Model for JARVIS
Autonomous cron and recurring scheduler database table.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from jarvis.db.models.base import Base, GUID, UniversalJSON


class ScheduleModel(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    task_name: Mapped[str] = mapped_column(sa.String(150), index=True, nullable=False)
    cron_expression: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, default=True, index=True, nullable=False)
    last_run: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    next_run: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), index=True, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)

