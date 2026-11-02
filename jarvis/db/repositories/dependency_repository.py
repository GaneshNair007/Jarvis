"""
JARVIS Task Dependency Repository
Manages Directed Acyclic Graph edges between tasks and checks satisfaction.
"""

from __future__ import annotations

import uuid
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.dependency import TaskDependencyModel
from jarvis.db.models.task import TaskModel
from jarvis.db.repositories.base import BaseRepository


class DependencyRepository(BaseRepository[TaskDependencyModel]):

    def __init__(self, session: Session):
        super().__init__(session, TaskDependencyModel)

    def add_dependency(self, task_id: uuid.UUID, depends_on_task_id: uuid.UUID) -> TaskDependencyModel:
        """Adds a directed dependency edge (task_id depends on depends_on_task_id)."""
        existing = (
            self.session.query(TaskDependencyModel)
            .filter(
                TaskDependencyModel.task_id == task_id,
                TaskDependencyModel.depends_on_task_id == depends_on_task_id,
            )
            .first()
        )
        if existing:
            return existing

        dep = TaskDependencyModel(
            id=uuid.uuid4(),
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
        )
        self.session.add(dep)
        return dep

    def get_dependencies(self, task_id: uuid.UUID) -> List[TaskDependencyModel]:
        """Returns all parent tasks that the given task depends on."""
        return (
            self.session.query(TaskDependencyModel)
            .filter(TaskDependencyModel.task_id == task_id)
            .all()
        )

    def get_downstream_tasks(self, task_id: uuid.UUID) -> List[TaskDependencyModel]:
        """Returns all child tasks that depend on the given task."""
        return (
            self.session.query(TaskDependencyModel)
            .filter(TaskDependencyModel.depends_on_task_id == task_id)
            .all()
        )

    def dependency_satisfied(self, task_id: uuid.UUID) -> bool:
        """Returns True if 100% of the tasks this task depends on are COMPLETED."""
        deps = self.get_dependencies(task_id)
        if not deps:
            return True

        for d in deps:
            parent = self.session.query(TaskModel).filter(TaskModel.id == d.depends_on_task_id).first()
            if not parent or parent.status != "COMPLETED":
                return False
        return True
