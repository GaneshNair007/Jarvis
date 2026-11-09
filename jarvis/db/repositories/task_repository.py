"""
JARVIS Task Repository
Heart of DAG state management. Handles task persistence, readiness queries,
and DAG unblocking evaluation.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.task import TaskModel, TaskGraphModel
from jarvis.db.models.dependency import TaskDependencyModel
from jarvis.db.repositories.base import BaseRepository


class TaskRepository(BaseRepository[TaskModel]):
    def __init__(self, session: Session):
        super().__init__(session, TaskModel)

    def create_task_graph(
        self,
        goal_id: uuid.UUID,
        graph_name: str = "default_dag",
        metadata: Optional[Dict[str, Any]] = None,
        graph_id: Optional[uuid.UUID] = None,
    ) -> TaskGraphModel:
        """Creates a TaskGraph metadata record."""
        graph = TaskGraphModel(
            id=graph_id or uuid.uuid4(),
            goal_id=goal_id,
            graph_name=graph_name,
            status="PENDING",
            metadata_json=metadata or {},
        )
        self.session.add(graph)
        return graph

    def get_task_graph(self, graph_id: uuid.UUID) -> Optional[TaskGraphModel]:
        return self.session.query(TaskGraphModel).filter(TaskGraphModel.id == graph_id).first()

    def create_task(
        self,
        task_graph_id: uuid.UUID,
        goal_id: uuid.UUID,
        task_key: str,
        name: str,
        description: str,
        department: str,
        priority: str = "MEDIUM",
        assigned_agent: Optional[str] = None,
        tool_requirements: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        task_id: Optional[uuid.UUID] = None,
    ) -> TaskModel:
        """Creates a single TaskModel in the DAG."""
        task = TaskModel(
            id=task_id or uuid.uuid4(),
            task_graph_id=task_graph_id,
            goal_id=goal_id,
            task_key=task_key,
            name=name,
            description=description,
            department=department.lower(),
            priority=priority.upper(),
            status="PENDING",
            assigned_agent=assigned_agent,
            tool_requirements=tool_requirements or [],
            outputs={},
            metadata_json=metadata or {},
        )
        self.session.add(task)
        return task

    def get_task(self, task_id: uuid.UUID) -> Optional[TaskModel]:
        return self.session.query(TaskModel).filter(TaskModel.id == task_id).first()

    def get_task_by_key(self, task_graph_id: uuid.UUID, task_key: str) -> Optional[TaskModel]:
        return (
            self.session.query(TaskModel)
            .filter(TaskModel.task_graph_id == task_graph_id, TaskModel.task_key == task_key)
            .first()
        )

    def get_tasks_by_graph(self, task_graph_id: uuid.UUID) -> List[TaskModel]:
        return self.session.query(TaskModel).filter(TaskModel.task_graph_id == task_graph_id).all()

    def get_ready_tasks(self, task_graph_id: Optional[uuid.UUID] = None) -> List[TaskModel]:
        query = self.session.query(TaskModel).filter(TaskModel.status == "READY")
        if task_graph_id:
            query = query.filter(TaskModel.task_graph_id == task_graph_id)
        return query.all()

    def get_running_tasks(self, task_graph_id: Optional[uuid.UUID] = None) -> List[TaskModel]:
        query = self.session.query(TaskModel).filter(TaskModel.status == "RUNNING")
        if task_graph_id:
            query = query.filter(TaskModel.task_graph_id == task_graph_id)
        return query.all()

    def update_task_status(
        self,
        task_id: uuid.UUID,
        status: str,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaskModel]:
        task = self.get_task(task_id)
        if task:
            task.status = status.upper()
            if outputs:
                new_outputs = dict(task.outputs)
                new_outputs.update(outputs)
                task.outputs = new_outputs
            if status.upper() == "COMPLETED":
                task.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.session.add(task)
        return task

    def get_unblocked_tasks(self, task_graph_id: uuid.UUID) -> List[TaskModel]:
        """
        Special DAG Query:
        Inspects all PENDING, READY, or BLOCKED tasks in the task graph.
        For each task, evaluates all required dependencies:
          - If 100% of dependencies are COMPLETED -> sets/confirms status READY and includes in output.
          - If any dependency is not COMPLETED -> marks BLOCKED.
        """
        candidate_tasks = (
            self.session.query(TaskModel)
            .filter(
                TaskModel.task_graph_id == task_graph_id,
                TaskModel.status.in_(["PENDING", "READY", "BLOCKED"]),
            )
            .all()
        )

        unblocked: List[TaskModel] = []
        for task in candidate_tasks:
            # Query dependencies of this task
            deps = self.session.query(TaskDependencyModel).filter(TaskDependencyModel.task_id == task.id).all()

            if not deps:
                # No dependencies -> immediately unblocked
                if task.status != "READY":
                    task.status = "READY"
                    self.session.add(task)
                unblocked.append(task)
            else:
                # Check status of every dependency
                all_done = True
                for d in deps:
                    parent_task = self.session.query(TaskModel).filter(TaskModel.id == d.depends_on_task_id).first()
                    if not parent_task or parent_task.status != "COMPLETED":
                        all_done = False
                        break

                if all_done:
                    if task.status != "READY":
                        task.status = "READY"
                        self.session.add(task)
                    unblocked.append(task)
                else:
                    if task.status != "BLOCKED":
                        task.status = "BLOCKED"
                        self.session.add(task)

        return unblocked
