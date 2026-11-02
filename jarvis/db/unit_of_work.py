"""
JARVIS Unit of Work Pattern
Coordinates multiple repository operations within an atomic ACID transaction.
Guarantees transaction rollback, consistency, and clean session lifecycle management.
"""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from jarvis.db.session import SessionFactory
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
from jarvis.core.logger import get_logger

logger = get_logger("db.uow")


class UnitOfWork:
    """
    Context manager providing transactional access to all domain repositories.
    Usage:
        with UnitOfWork() as uow:
            goal = uow.goals.create_goal(title="Win AI Hackathon")
            task = uow.tasks.create_task(goal_id=goal.id, name="Scout Rules")
            uow.commit()
    """

    def __init__(self, session: Optional[Session] = None):
        self._external_session = session is not None
        self.session: Session = session or SessionFactory()

        # Lazy instantiated repository caches
        self._goals: Optional[GoalRepository] = None
        self._tasks: Optional[TaskRepository] = None
        self._dependencies: Optional[DependencyRepository] = None
        self._agents: Optional[AgentRepository] = None
        self._assignments: Optional[AssignmentRepository] = None
        self._executions: Optional[ExecutionRepository] = None
        self._memories: Optional[MemoryRepository] = None
        self._reflections: Optional[ReflectionRepository] = None
        self._opportunities: Optional[OpportunityRepository] = None
        self._schedules: Optional[SchedulerRepository] = None
        self._artifacts: Optional[ArtifactRepository] = None
        self._knowledge: Optional[KnowledgeGraphRepository] = None
        self._audits: Optional[AuditRepository] = None

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            logger.error(f"UnitOfWork transaction rolled back due to error: {exc_val}")
            self.rollback()
        if not self._external_session:
            self.session.close()

    def commit(self) -> None:
        """Commits transaction to database."""
        self.session.commit()

    def rollback(self) -> None:
        """Rolls back uncommitted session changes."""
        self.session.rollback()

    def flush(self) -> None:
        """Flushes pending changes to obtain generated IDs without committing."""
        self.session.flush()

    # Repositories
    @property
    def goals(self) -> GoalRepository:
        if self._goals is None:
            self._goals = GoalRepository(self.session)
        return self._goals

    @property
    def tasks(self) -> TaskRepository:
        if self._tasks is None:
            self._tasks = TaskRepository(self.session)
        return self._tasks

    @property
    def dependencies(self) -> DependencyRepository:
        if self._dependencies is None:
            self._dependencies = DependencyRepository(self.session)
        return self._dependencies

    @property
    def agents(self) -> AgentRepository:
        if self._agents is None:
            self._agents = AgentRepository(self.session)
        return self._agents

    @property
    def assignments(self) -> AssignmentRepository:
        if self._assignments is None:
            self._assignments = AssignmentRepository(self.session)
        return self._assignments

    @property
    def executions(self) -> ExecutionRepository:
        if self._executions is None:
            self._executions = ExecutionRepository(self.session)
        return self._executions

    @property
    def memories(self) -> MemoryRepository:
        if self._memories is None:
            self._memories = MemoryRepository(self.session)
        return self._memories

    @property
    def reflections(self) -> ReflectionRepository:
        if self._reflections is None:
            self._reflections = ReflectionRepository(self.session)
        return self._reflections

    @property
    def opportunities(self) -> OpportunityRepository:
        if self._opportunities is None:
            self._opportunities = OpportunityRepository(self.session)
        return self._opportunities

    @property
    def schedules(self) -> SchedulerRepository:
        if self._schedules is None:
            self._schedules = SchedulerRepository(self.session)
        return self._schedules

    @property
    def artifacts(self) -> ArtifactRepository:
        if self._artifacts is None:
            self._artifacts = ArtifactRepository(self.session)
        return self._artifacts

    @property
    def knowledge(self) -> KnowledgeGraphRepository:
        if self._knowledge is None:
            self._knowledge = KnowledgeGraphRepository(self.session)
        return self._knowledge

    @property
    def audits(self) -> AuditRepository:
        if self._audits is None:
            self._audits = AuditRepository(self.session)
        return self._audits

