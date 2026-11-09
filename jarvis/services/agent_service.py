"""
JARVIS Agent Workforce Service
Enables dynamic on-demand agent lifecycle management:
Spawns, pauses, resumes, and retires specialized AI agents instead of idling 100+ permanent processes.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from jarvis.db.unit_of_work import UnitOfWork
from jarvis.db.models.agent import AgentModel
from jarvis.db.events import event_bus, AgentLifecycleEvent
from jarvis.db.redis_state import redis_state_store
from jarvis.core.logger import get_logger

logger = get_logger("services.agent")


class AgentService:
    """Service layer managing dynamic agent lifecycles and roster allocation."""

    def __init__(self, uow_factory=UnitOfWork):
        self.uow_factory = uow_factory

    def spawn_worker_agent(
        self,
        agent_key: str,
        name: str,
        role: str,
        department_name: str,
        model_name: str = "gemini-2.5-pro",
        capabilities: Optional[List[str]] = None,
    ) -> AgentModel:
        """Dynamically instantiates and persists a specialized AI worker agent."""
        with self.uow_factory() as uow:
            # Check or resolve department
            dept = uow.session.query(uow.departments.model_class).filter_by(name=department_name).first()
            dept_id = dept.id if dept else None

            agent = uow.agents.register_agent(
                agent_key=agent_key,
                name=name,
                role=role,
                department_id=dept_id,
                model_name=model_name,
                capabilities=capabilities or [],
            )
            uow.commit()

            # Broadcast lifecycle event
            event_bus.publish(
                AgentLifecycleEvent(
                    agent_id=str(agent.id),
                    state="created",
                    reason=f"Dynamically spawned agent [{agent_key}] for department [{department_name}].",
                )
            )

            # Initialize live Redis state
            redis_state_store.set_agent_status(
                department=department_name,
                agent_name=agent_key,
                status="IDLE",
                current_task="initialized",
                progress=0,
            )

            logger.info(f"Dynamically spawned worker agent '{name}' ({agent.id}) on model '{model_name}'.")
            return agent

    def pause_agent(self, agent_id: uuid.UUID, reason: str = "Resource reclamation") -> Optional[AgentModel]:
        """Pauses worker agent execution and frees resources."""
        with self.uow_factory() as uow:
            agent = uow.agents.update_status(agent_id, "PAUSED", reason=reason)
            if agent:
                event_bus.publish(
                    AgentLifecycleEvent(
                        agent_id=str(agent.id),
                        state="paused",
                        reason=reason,
                    )
                )
            uow.commit()
            return agent

    def resume_agent(self, agent_id: uuid.UUID) -> Optional[AgentModel]:
        """Resumes a paused agent back to active duty."""
        with self.uow_factory() as uow:
            agent = uow.agents.update_status(agent_id, "ACTIVE", reason="Resumed to active fleet")
            if agent:
                event_bus.publish(
                    AgentLifecycleEvent(
                        agent_id=str(agent.id),
                        state="resumed",
                        reason="Resumed to active fleet",
                    )
                )
            uow.commit()
            return agent

    def retire_agent(self, agent_id: uuid.UUID, reason: str = "Goal achieved") -> Optional[AgentModel]:
        """Retires a worker agent, preserving full audit history while decommissioning."""
        with self.uow_factory() as uow:
            agent = uow.agents.update_status(agent_id, "RETIRED", reason=reason)
            if agent:
                event_bus.publish(
                    AgentLifecycleEvent(
                        agent_id=str(agent.id),
                        state="retired",
                        reason=reason,
                    )
                )
            uow.commit()
            return agent

    def get_active_workforce(self) -> List[AgentModel]:
        with self.uow_factory() as uow:
            return uow.agents.get_available_agents()
