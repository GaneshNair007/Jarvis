"""
Reflection Repository
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.reflection import ReflectionModel
from db.repositories.base import BaseRepository


class ReflectionRepository(BaseRepository[ReflectionModel]):
    def __init__(self, session: Session):
        super().__init__(session, ReflectionModel)

    def get_by_goal(self, goal_id: uuid.UUID | str) -> List[ReflectionModel]:
        if isinstance(goal_id, str):
            goal_id = uuid.UUID(goal_id)
        stmt = (
            sa.select(ReflectionModel)
            .where(ReflectionModel.goal_id == goal_id)
            .order_by(ReflectionModel.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def record_reflection(
        self,
        goal_id: uuid.UUID | str,
        successes: List[str],
        failures: List[str],
        improvements: List[str],
        opportunities: List[str],
        metrics: Dict[str, Any],
        constitution_alignment_score: float = 1.0,
    ) -> ReflectionModel:
        if isinstance(goal_id, str):
            goal_id = uuid.UUID(goal_id)

        reflection = ReflectionModel(
            goal_id=goal_id,
            successes=successes,
            failures=failures,
            improvements=improvements,
            opportunities=opportunities,
            metrics=metrics,
            constitution_alignment_score=constitution_alignment_score,
        )
        return self.create(reflection)
