"""
JARVIS Goal Service
Coordinates strategic goal creation, DAG decomposition ingestion, and completion events.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from jarvis.db.unit_of_work import UnitOfWork
from jarvis.db.models.goal import GoalModel
from jarvis.db.events import event_bus, GoalCompletedEvent
from jarvis.core.task_graph import TaskGraph, TaskNode
from jarvis.core.logger import get_logger

logger = get_logger("services.goal")


class GoalService:
    """Service layer orchestrating Goal lifecycle and DAG persistence."""

    def __init__(self, uow_factory=UnitOfWork):
        self.uow_factory = uow_factory

    def create_goal(
        self,
        title: str,
        description: str = "",
        priority: str = "HIGH",
        created_by: str = "ganesh",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GoalModel:
        with self.uow_factory() as uow:
            goal = uow.goals.create_goal(
                title=title,
                description=description,
                priority=priority,
                created_by=created_by,
                metadata=metadata,
            )
            uow.audits.record_audit(
                action="CREATE_GOAL",
                target=f"Goal:{goal.id}",
                metadata={"title": title, "priority": priority},
            )
            uow.commit()
            logger.info(f"Goal '{title}' ({goal.id}) successfully created and persisted.")
            return goal

    def store_task_graph_dag(
        self,
        goal_id: uuid.UUID,
        graph: TaskGraph,
    ) -> uuid.UUID:
        """
        Ingests in-memory TaskGraph DAG into relational database models:
        1. Creates TaskGraphModel
        2. Creates TaskModel for each node
        3. Creates TaskDependencyModel for each edge
        All executed atomically within a single UnitOfWork transaction.
        """
        with self.uow_factory() as uow:
            db_graph = uow.tasks.create_task_graph(
                goal_id=goal_id,
                graph_name=f"DAG_{graph.goal_id}",
                metadata={"total_nodes": len(graph.nodes)},
            )
            uow.flush()

            # Map in-memory task_id (str) -> database task_id (UUID)
            key_to_uuid: Dict[str, uuid.UUID] = {}

            # 1. Insert tasks
            for node in graph.nodes.values():
                db_task = uow.tasks.create_task(
                    task_graph_id=db_graph.id,
                    goal_id=goal_id,
                    task_key=node.task_id,
                    name=node.name,
                    description=node.description,
                    department=node.department,
                    priority=node.priority.value,
                    assigned_agent=node.assigned_agent,
                    tool_requirements=node.tool_requirements,
                    metadata=node.metadata,
                )
                uow.flush()
                key_to_uuid[node.task_id] = db_task.id

            # 2. Insert dependency edges
            for node in graph.nodes.values():
                child_uuid = key_to_uuid[node.task_id]
                for dep_key in node.dependencies:
                    if dep_key in key_to_uuid:
                        parent_uuid = key_to_uuid[dep_key]
                        uow.dependencies.add_dependency(
                            task_id=child_uuid,
                            depends_on_task_id=parent_uuid,
                        )

            uow.commit()
            logger.info(f"Persisted DAG '{graph.goal_id}' with {len(graph.nodes)} tasks into TaskGraph ({db_graph.id}).")
            return db_graph.id

    def complete_goal(self, goal_id: uuid.UUID) -> Optional[GoalModel]:
        with self.uow_factory() as uow:
            goal = uow.goals.update_status(goal_id, "COMPLETED")
            if goal:
                tasks = uow.tasks.session.query(uow.tasks.model_class).filter_by(goal_id=goal_id).all()
                event_bus.publish(GoalCompletedEvent(
                    goal_id=str(goal.id),
                    title=goal.title,
                    total_tasks=len(tasks),
                ))
            uow.commit()
            return goal

