"""
JARVIS Audit Repository
Manages immutable operational audit records across agents, files, and system tools.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.audit import AuditModel
from jarvis.db.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditModel]):

    def __init__(self, session: Session):
        super().__init__(session, AuditModel)

    def record_audit(
        self,
        action: str,
        target: str,
        actor: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        audit_id: Optional[uuid.UUID] = None,
    ) -> AuditModel:
        """Appends an immutable audit event."""
        event = AuditModel(
            id=audit_id or uuid.uuid4(),
            actor=actor,
            action=action,
            target=target,
            metadata_json=metadata or {},
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(event)
        return event

    def get_recent_audits(self, limit: int = 50) -> List[AuditModel]:
        return (
            self.session.query(AuditModel)
            .order_by(AuditModel.timestamp.desc())
            .limit(limit)
            .all()
        )

    def search_audits(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditModel]:
        query = self.session.query(AuditModel)
        if actor:
            query = query.filter(AuditModel.actor == actor)
        if action:
            query = query.filter(AuditModel.action == action)
        return query.order_by(AuditModel.timestamp.desc()).limit(limit).all()

