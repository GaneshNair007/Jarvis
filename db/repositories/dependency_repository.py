"""
Task Dependency Repository
"""

from __future__ import annotations

import uuid
from typing import List
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.dependency import TaskDependencyModel
from db.repositories.base import BaseRepository


class DependencyRepository(BaseRepository[TaskDependencyModel]):
    def __init__(self, session: Session):
        super().__init__(session, TaskDependencyModel)

    def get_dependencies_for_task(self, task_id: uuid.UUID | str) -> List[TaskDependencyModel]:
        if isinstance(task_id, str):
            task_id = uuid.UUID(task_id)
        stmt = sa.select(TaskDependencyModel).where(TaskDependencyModel.task_id == task_id)
        return list(self.session.scalars(stmt).all())

    def get_dependents(self, parent_task_id: uuid.UUID | str) -> List[TaskDependencyModel]:
        if isinstance(parent_task_id, str):
            parent_task_id = uuid.UUID(parent_task_id)
        stmt = sa.select(TaskDependencyModel).where(TaskDependencyModel.depends_on_task_id == parent_task_id)
        return list(self.session.scalars(stmt).all())

    def add_dependency(self, task_id: uuid.UUID | str, depends_on_task_id: uuid.UUID | str) -> TaskDependencyModel:
        if isinstance(task_id, str):
            task_id = uuid.UUID(task_id)
        if isinstance(depends_on_task_id, str):
            depends_on_task_id = uuid.UUID(depends_on_task_id)
        dep = TaskDependencyModel(task_id=task_id, depends_on_task_id=depends_on_task_id)
        return self.create(dep)
