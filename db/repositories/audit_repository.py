"""
Audit Repository
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.audit_event import AuditEventModel
from db.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditEventModel]):
    def __init__(self, session: Session):
        super().__init__(session, AuditEventModel)

    def log_event(
        self,
        event_type: str,
        actor: str,
        resource_type: str,
        action: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEventModel:
        event = AuditEventModel(
            event_type=event_type,
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details or {},
        )
        return self.create(event)

    def list_recent(self, limit: int = 50) -> List[AuditEventModel]:
        stmt = sa.select(AuditEventModel).order_by(AuditEventModel.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())
