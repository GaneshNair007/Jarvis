"""
SQLAlchemy 2.x Task and TaskGraph Models for JARVIS
Heart of the DAG execution hierarchy and state machine.
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.models.base import Base, GUID, UniversalJSON, TimestampMixin

if TYPE_CHECKING:
    from jarvis.db.models.artifact import ArtifactModel
    from jarvis.db.models.assignment import AssignmentModel
    from jarvis.db.models.dependency import TaskDependencyModel
    from jarvis.db.models.execution import ExecutionModel
    from jarvis.db.models.goal import GoalModel


class TaskGraphModel(Base, TimestampMixin):
    __tablename__ = "task_graphs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False)
    graph_name: Mapped[str] = mapped_column(sa.String(255), default="default_dag", nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), default="PENDING", index=True, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)

    # Relationships
    goal: Mapped["GoalModel"] = relationship("GoalModel", back_populates="task_graphs")
    tasks: Mapped[List["TaskModel"]] = relationship("TaskModel", back_populates="task_graph", cascade="all, delete-orphan")


class TaskModel(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    task_graph_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("task_graphs.id", ondelete="CASCADE"), index=True, nullable=False)
    goal_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False)
    parent_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID, nullable=True)
    task_key: Mapped[str] = mapped_column(sa.String(100), index=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    department: Mapped[str] = mapped_column(sa.String(50), index=True, nullable=False)
    assigned_agent: Mapped[Optional[str]] = mapped_column(sa.String(100), index=True, nullable=True)
    priority: Mapped[str] = mapped_column(sa.String(20), default="MEDIUM", index=True, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), default="PENDING", index=True, nullable=False)
    retry_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(sa.Integer, default=3, nullable=False)
    tool_requirements: Mapped[List[str]] = mapped_column(UniversalJSON, default=list, nullable=False)
    outputs: Mapped[Dict[str, Any]] = mapped_column(UniversalJSON, default=dict, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    # Relationships
    task_graph: Mapped["TaskGraphModel"] = relationship("TaskGraphModel", back_populates="tasks")
    goal: Mapped["GoalModel"] = relationship("GoalModel", back_populates="tasks")
    assignments: Mapped[List["AssignmentModel"]] = relationship("AssignmentModel", back_populates="task", cascade="all, delete-orphan")
    executions: Mapped[List["ExecutionModel"]] = relationship("ExecutionModel", back_populates="task", cascade="all, delete-orphan")
    artifacts: Mapped[List["ArtifactModel"]] = relationship("ArtifactModel", back_populates="task", cascade="all, delete-orphan")
    dependencies: Mapped[List["TaskDependencyModel"]] = relationship(
        "TaskDependencyModel",
        foreign_keys="TaskDependencyModel.task_id",
        back_populates="task",
        cascade="all, delete-orphan",
    )
    dependents: Mapped[List["TaskDependencyModel"]] = relationship(
        "TaskDependencyModel",
        foreign_keys="TaskDependencyModel.depends_on_task_id",
        back_populates="depends_on_task",
        cascade="all, delete-orphan",
    )

