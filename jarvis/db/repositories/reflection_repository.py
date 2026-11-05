"""
JARVIS Reflection Repository
Stores and retrieves post-goal retrospective analyses for continuous learning.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.reflection import ReflectionModel
from jarvis.db.repositories.base import BaseRepository


class ReflectionRepository(BaseRepository[ReflectionModel]):

    def __init__(self, session: Session):
        super().__init__(session, ReflectionModel)

    def add_reflection(
        self,
        goal_id: uuid.UUID,
        successes: List[str],
        failures: List[str],
        improvements: List[str],
        opportunities: List[str],
        metrics: Optional[Dict[str, Any]] = None,
        reflection_id: Optional[uuid.UUID] = None,
    ) -> ReflectionModel:
        """Stores a post-goal retrospective record."""
        refl = ReflectionModel(
            id=reflection_id or uuid.uuid4(),
            goal_id=goal_id,
            successes=successes,
            failures=failures,
            improvements=improvements,
            opportunities=opportunities,
            metrics=metrics or {},
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(refl)
        return refl

    def get_reflections(self, limit: int = 10) -> List[ReflectionModel]:
        return (
            self.session.query(ReflectionModel)
            .order_by(ReflectionModel.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_goal_reflections(self, goal_id: uuid.UUID) -> List[ReflectionModel]:
        return (
            self.session.query(ReflectionModel)
            .filter(ReflectionModel.goal_id == goal_id)
            .order_by(ReflectionModel.created_at.desc())
            .all()
        )

    def get_latest_reflection(self) -> Optional[ReflectionModel]:
        return (
            self.session.query(ReflectionModel)
            .order_by(ReflectionModel.created_at.desc())
            .first()
        )

