"""
JARVIS Goal Repository
Handles persistence and lifecycle queries for high-level Goal objects.
"""

from __future__ import annotations

import uuid
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.goal import GoalModel
from jarvis.db.repositories.base import BaseRepository


class GoalRepository(BaseRepository[GoalModel]):
    def __init__(self, session: Session):
        super().__init__(session, GoalModel)

    def create_goal(
        self,
        title: str,
        description: str = "",
        created_by: str = "ganesh",
        priority: str = "HIGH",
        metadata: Optional[dict] = None,
        goal_id: Optional[uuid.UUID] = None,
    ) -> GoalModel:
        """Creates and stores a new high-level strategic goal."""
        goal = GoalModel(
            id=goal_id or uuid.uuid4(),
            title=title,
            description=description,
            created_by=created_by,
            priority=priority.upper(),
            status="PENDING",
            metadata_json=metadata or {},
        )
        self.session.add(goal)
        return goal

    def get_goal(self, goal_id: uuid.UUID) -> Optional[GoalModel]:
        """Retrieves goal by UUID."""
        return self.session.query(GoalModel).filter(GoalModel.id == goal_id).first()

    def update_status(self, goal_id: uuid.UUID, status: str) -> Optional[GoalModel]:
        """Updates lifecycle state of goal."""
        goal = self.get_goal(goal_id)
        if goal:
            goal.status = status.upper()
            self.session.add(goal)
        return goal

    def list_goals(self, status: Optional[str] = None, limit: int = 50) -> List[GoalModel]:
        """Queries goals with optional status filtering."""
        query = self.session.query(GoalModel)
        if status:
            query = query.filter(GoalModel.status == status.upper())
        return query.order_by(GoalModel.created_at.desc()).limit(limit).all()

    def get_active_goals(self) -> List[GoalModel]:
        """Returns all goals currently in PENDING or RUNNING status."""
        return self.session.query(GoalModel).filter(GoalModel.status.in_(["PENDING", "RUNNING"])).all()
