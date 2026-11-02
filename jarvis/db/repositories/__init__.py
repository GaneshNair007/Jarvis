"""
JARVIS Repositories Package
Exposes all domain repositories strictly adhering to Domain-Driven Architecture.
"""

from jarvis.db.repositories.base import BaseRepository
from jarvis.db.repositories.goal_repository import GoalRepository
from jarvis.db.repositories.task_repository import TaskRepository
from jarvis.db.repositories.dependency_repository import DependencyRepository
from jarvis.db.repositories.agent_repository import AgentRepository
from jarvis.db.repositories.assignment_repository import AssignmentRepository
from jarvis.db.repositories.execution_repository import ExecutionRepository
from jarvis.db.repositories.memory_repository import MemoryRepository
from jarvis.db.repositories.reflection_repository import ReflectionRepository
from jarvis.db.repositories.opportunity_repository import OpportunityRepository
from jarvis.db.repositories.scheduler_repository import SchedulerRepository
from jarvis.db.repositories.artifact_repository import ArtifactRepository
from jarvis.db.repositories.graph_repository import KnowledgeGraphRepository
from jarvis.db.repositories.audit_repository import AuditRepository

__all__ = [
    "BaseRepository",
    "GoalRepository",
    "TaskRepository",
    "DependencyRepository",
    "AgentRepository",
    "AssignmentRepository",
    "ExecutionRepository",
    "MemoryRepository",
    "ReflectionRepository",
    "OpportunityRepository",
    "SchedulerRepository",
    "ArtifactRepository",
    "KnowledgeGraphRepository",
    "AuditRepository",
]

