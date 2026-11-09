"""
Task Repository
"""

from __future__ import annotations

import uuid
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from db.models.task import TaskModel
from db.repositories.base import BaseRepository


class TaskRepository(BaseRepository[TaskModel]):
    def __init__(self, session: Session):
        super().__init__(session, TaskModel)

    def get_by_goal(self, goal_id: uuid.UUID | str) -> List[TaskModel]:
        if isinstance(goal_id, str):
            goal_id = uuid.UUID(goal_id)
        stmt = sa.select(TaskModel).where(TaskModel.goal_id == goal_id)
        return list(self.session.scalars(stmt).all())

    def get_by_task_key(self, task_key: str, goal_id: Optional[uuid.UUID | str] = None) -> Optional[TaskModel]:
        stmt = sa.select(TaskModel).where(TaskModel.task_key == task_key)
        if goal_id:
            if isinstance(goal_id, str):
                goal_id = uuid.UUID(goal_id)
            stmt = stmt.where(TaskModel.goal_id == goal_id)
        return self.session.scalars(stmt).first()

    def update_status(
        self, task_id: uuid.UUID | str, status: str, outputs: Optional[dict] = None
    ) -> Optional[TaskModel]:
        task = self.get_by_id(task_id)
        if task:
            task.status = status
            if outputs:
                task.outputs = outputs
            self.session.flush()
        return task
