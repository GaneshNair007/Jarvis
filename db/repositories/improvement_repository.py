"""
Improvement Request Repository
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.improvement import ImprovementRequestModel
from db.repositories.base import BaseRepository


class ImprovementRepository(BaseRepository[ImprovementRequestModel]):
    def __init__(self, session: Session):
        super().__init__(session, ImprovementRequestModel)

    def list_by_status(self, status: str) -> List[ImprovementRequestModel]:
        stmt = sa.select(ImprovementRequestModel).where(ImprovementRequestModel.status == status)
        return list(self.session.scalars(stmt).all())

    def create_request(
        self,
        title: str,
        description: str,
        category: str = "architecture",
        priority: str = "MEDIUM",
        status: str = "PROPOSED",
        reflection_id: Optional[uuid.UUID | str] = None,
        capability_id: Optional[uuid.UUID | str] = None,
        proposed_changes: Optional[Dict[str, Any]] = None,
    ) -> ImprovementRequestModel:
        if reflection_id and isinstance(reflection_id, str):
            reflection_id = uuid.UUID(reflection_id)
        if capability_id and isinstance(capability_id, str):
            capability_id = uuid.UUID(capability_id)

        req = ImprovementRequestModel(
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=status,
            reflection_id=reflection_id,
            capability_id=capability_id,
            proposed_changes=proposed_changes or {},
        )
        return self.create(req)
