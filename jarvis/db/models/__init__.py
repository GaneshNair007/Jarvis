"""
JARVIS Database Models Package
Aggregates all SQLAlchemy ORM models for operational brain, workforce, memory, and knowledge graph.
"""

from jarvis.db.models.base import Base, GUID, UniversalJSON, TimestampMixin
from jarvis.db.models.goal import GoalModel
from jarvis.db.models.task import TaskGraphModel, TaskModel
from jarvis.db.models.dependency import TaskDependencyModel
from jarvis.db.models.department import DepartmentModel
from jarvis.db.models.agent import AgentModel
from jarvis.db.models.assignment import AssignmentModel
from jarvis.db.models.execution import ExecutionModel
from jarvis.db.models.memory import MemoryModel
from jarvis.db.models.reflection import ReflectionModel
from jarvis.db.models.opportunity import OpportunityModel
from jarvis.db.models.artifact import ArtifactModel
from jarvis.db.models.schedule import ScheduleModel
from jarvis.db.models.audit import AuditModel
from jarvis.db.models.knowledge import KnowledgeNodeModel, KnowledgeEdgeModel
from jarvis.db.models.lifecycle import AgentLifecycleModel
from jarvis.db.models.workspace import (
    WorkspaceAssignmentModel,
    WorkspaceCaptureModel,
    WorkspaceCourseModel,
    WorkspaceTaskModel,
)

__all__ = [
    "Base",
    "GUID",
    "UniversalJSON",
    "TimestampMixin",
    "GoalModel",
    "TaskGraphModel",
    "TaskModel",
    "TaskDependencyModel",
    "DepartmentModel",
    "AgentModel",
    "AssignmentModel",
    "ExecutionModel",
    "MemoryModel",
    "ReflectionModel",
    "OpportunityModel",
    "ArtifactModel",
    "ScheduleModel",
    "AuditModel",
    "KnowledgeNodeModel",
    "KnowledgeEdgeModel",
    "AgentLifecycleModel",
    "WorkspaceCourseModel",
    "WorkspaceAssignmentModel",
    "WorkspaceTaskModel",
    "WorkspaceCaptureModel",
]
