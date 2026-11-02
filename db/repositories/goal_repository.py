"""
Goal Repository
"""

from __future__ import annotations

import uuid
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from db.models.goal import GoalModel
from db.repositories.base import BaseRepository


class GoalRepository(BaseRepository[GoalModel]):
    def __init__(self, session: Session):
        super().__init__(session, GoalModel)

    def get_with_tasks(self, goal_id: uuid.UUID | str) -> Optional[GoalModel]:
        """Fetch goal eagerly with associated tasks."""
        if isinstance(goal_id, str):
            goal_id = uuid.UUID(goal_id)
        stmt = (
            sa.select(GoalModel)
            .where(GoalModel.id == goal_id)
            .options(joinedload(GoalModel.tasks))
        )
        return self.session.scalars(stmt).unique().first()

    def get_by_status(self, status: str) -> List[GoalModel]:
        return self.list(status=status)
