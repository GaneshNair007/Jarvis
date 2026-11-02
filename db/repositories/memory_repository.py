"""
Memory Repository
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.memory import MemoryModel
from db.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[MemoryModel]):
    def __init__(self, session: Session):
        super().__init__(session, MemoryModel)

    def search_by_category(self, category: str, limit: int = 50) -> List[MemoryModel]:
        stmt = (
            sa.select(MemoryModel)
            .where(MemoryModel.category == category)
            .order_by(MemoryModel.importance_score.desc(), MemoryModel.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def record_memory(
        self,
        category: str,
        content: Dict[str, Any],
        source_task_id: Optional[uuid.UUID | str] = None,
        goal_id: Optional[uuid.UUID | str] = None,
        importance_score: float = 1.0,
    ) -> MemoryModel:
        if source_task_id and isinstance(source_task_id, str):
            source_task_id = uuid.UUID(source_task_id)
        if goal_id and isinstance(goal_id, str):
            goal_id = uuid.UUID(goal_id)

        memory = MemoryModel(
            category=category,
            content=content,
            source_task_id=source_task_id,
            goal_id=goal_id,
            importance_score=importance_score,
        )
        return self.create(memory)
