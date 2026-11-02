"""
JARVIS Agent Repository
Stores workforce roster, dynamic agent provisioning, and lifecycle state tracking
(created, paused, resumed, retired).
"""

from __future__ import annotations

import datetime
import uuid
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.agent import AgentModel
from jarvis.db.models.lifecycle import AgentLifecycleModel
from jarvis.db.repositories.base import BaseRepository


class AgentRepository(BaseRepository[AgentModel]):

    def __init__(self, session: Session):
        super().__init__(session, AgentModel)

    def register_agent(
        self,
        agent_key: str,
        name: str,
        role: str,
        department_id: Optional[uuid.UUID] = None,
        model_name: str = "gemini-2.5-pro",
        capabilities: Optional[List[str]] = None,
        agent_id: Optional[uuid.UUID] = None,
    ) -> AgentModel:
        """Registers a worker agent and records initial CREATED lifecycle event."""
        existing = self.get_agent_by_key(agent_key)
        if existing:
            return existing

        aid = agent_id or uuid.uuid4()
        agent = AgentModel(
            id=aid,
            agent_key=agent_key.lower(),
            name=name,
            role=role,
            department_id=department_id,
            model_name=model_name,
            status="ACTIVE",
            capabilities=capabilities or [],
        )
        self.session.add(agent)

        # Record Lifecycle event
        self.record_lifecycle_event(
            agent_id=aid,
            state="created",
            reason="Worker agent registered into organizational roster.",
        )
        return agent

    def get_agent(self, agent_id: uuid.UUID) -> Optional[AgentModel]:
        return self.session.query(AgentModel).filter(AgentModel.id == agent_id).first()

    def get_agent_by_key(self, agent_key: str) -> Optional[AgentModel]:
        return self.session.query(AgentModel).filter(AgentModel.agent_key == agent_key.lower()).first()

    def get_department_agents(self, department_id: uuid.UUID) -> List[AgentModel]:
        return (
            self.session.query(AgentModel)
            .filter(AgentModel.department_id == department_id)
            .all()
        )

    def get_available_agents(self) -> List[AgentModel]:
        return (
            self.session.query(AgentModel)
            .filter(AgentModel.status == "ACTIVE")
            .all()
        )

    def update_status(self, agent_id: uuid.UUID, status: str, reason: str = "") -> Optional[AgentModel]:
        """Transitions agent state (e.g. ACTIVE -> PAUSED / RETIRED) and writes lifecycle record."""
        agent = self.get_agent(agent_id)
        if agent:
            prev_status = agent.status
            agent.status = status.upper()
            self.session.add(agent)

            lifecycle_state = status.lower()
            if lifecycle_state not in ("created", "paused", "resumed", "retired"):
                lifecycle_state = "updated"

            self.record_lifecycle_event(
                agent_id=agent.id,
                state=lifecycle_state,
                reason=reason or f"State changed from {prev_status} to {agent.status}",
            )
        return agent

    def record_lifecycle_event(
        self,
        agent_id: uuid.UUID,
        state: str,
        reason: str = "",
    ) -> AgentLifecycleModel:
        """Appends an immutable lifecycle transition entry."""
        event = AgentLifecycleModel(
            id=uuid.uuid4(),
            agent_id=agent_id,
            state=state.lower(),
            reason=reason,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(event)
        return event

    def get_lifecycle_history(self, agent_id: uuid.UUID) -> List[AgentLifecycleModel]:
        """Returns ordered timeline of lifecycle state transitions for an agent."""
        return (
            self.session.query(AgentLifecycleModel)
            .filter(AgentLifecycleModel.agent_id == agent_id)
            .order_by(AgentLifecycleModel.timestamp.asc())
            .all()
        )
