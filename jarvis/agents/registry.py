"""
JARVIS Central Agent Registry (Milestone 2)
Provides unified discovery, lookup, alias resolution, and status monitoring
for all 8 specialized agents in the Iron Man JARVIS Personal AI Operating System.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from jarvis.agents.academic_tutor import AcademicTutorAgent, academic_tutor_agent
from jarvis.agents.base import BaseSpecialistAgent
from jarvis.agents.career_agent import CareerAgent, career_agent
from jarvis.agents.communication_agent import CommunicationAgent, communication_agent
from jarvis.agents.desktop_agent import DesktopAgent, desktop_agent
from jarvis.agents.engineer import EngineerAgent, engineer_agent
from jarvis.agents.productivity_agent import ProductivityAgent, productivity_agent
from jarvis.agents.researcher import ResearcherAgent, researcher_agent
from jarvis.agents.reviewer_agent import ReviewerAgent, reviewer_agent
from jarvis.core.logger import get_logger

logger = get_logger("agents.registry")


class AgentRegistry:
    """
    Central registry and discovery service for all 8 Iron Man JARVIS specialist agents.
    Supports canonical role lookups, class name lookups, and flexible aliases.
    """

    def __init__(self, auto_register: bool = True):
        self._agents: Dict[str, BaseSpecialistAgent] = {}
        self._aliases: Dict[str, str] = {}
        if auto_register:
            self._register_default_agents()

    def _register_default_agents(self) -> None:
        """Auto-registers all 8 specialist agents and standard pipeline aliases."""
        default_registrations = [
            (
                researcher_agent,
                ["researcher", "researcher_agent", "research"],
            ),
            (
                engineer_agent,
                ["engineer", "engineer_agent", "coder", "developer", "engineering"],
            ),
            (
                academic_tutor_agent,
                ["academic_tutor", "academic_tutor_agent", "tutor", "academic", "study_agent"],
            ),
            (
                career_agent,
                ["career", "career_agent", "gsoc_scout", "opportunity_scout", "career_scout"],
            ),
            (
                productivity_agent,
                ["productivity", "productivity_agent", "calendar", "calendar_agent", "scheduler"],
            ),
            (
                communication_agent,
                ["communication", "communication_agent", "email", "email_agent", "outbox_agent"],
            ),
            (
                desktop_agent,
                ["desktop", "desktop_agent", "desktop_operator", "app_launcher", "computer_use"],
            ),
            (
                reviewer_agent,
                ["reviewer", "reviewer_agent", "verifier", "critic", "critic_agent", "reviewer_critic"],
            ),
        ]

        for agent_inst, aliases in default_registrations:
            self.register_agent(agent_inst, aliases=aliases)

    def register_agent(
        self,
        agent: BaseSpecialistAgent,
        aliases: Optional[List[str]] = None,
    ) -> None:
        """Registers a specialist agent instance under its canonical name, role, and aliases."""
        canonical_key = agent.role.lower()
        name_key = agent.name.lower()

        self._agents[canonical_key] = agent
        self._agents[name_key] = agent

        if aliases:
            for alias in aliases:
                norm_alias = alias.lower().strip()
                self._aliases[norm_alias] = canonical_key

        logger.debug(f"Registered agent {agent.name} (role={agent.role}) with {len(aliases or [])} aliases")

    def register(self, agent: BaseSpecialistAgent, aliases: Optional[List[str]] = None) -> None:
        """Alias for register_agent."""
        self.register_agent(agent, aliases)

    def get_agent(self, name_or_alias: str) -> Optional[BaseSpecialistAgent]:
        """Resolves an agent instance by role, name, or alias (case-insensitive)."""
        if not name_or_alias or not isinstance(name_or_alias, str):
            return None

        key = name_or_alias.lower().strip()

        # 1. Direct match in registered agents
        if key in self._agents:
            return self._agents[key]

        # 2. Match via alias mapping
        if key in self._aliases:
            canonical = self._aliases[key]
            return self._agents.get(canonical)

        return None

    def list_agents(self) -> List[str]:
        """Returns sorted list of all unique canonical agent roles registered."""
        unique_roles = {agent.role for agent in self._agents.values()}
        return sorted(unique_roles)

    def get_all_agents(self) -> Dict[str, BaseSpecialistAgent]:
        """Returns a mapping of canonical role names to agent instances."""
        return {agent.role: agent for agent in self._agents.values()}

    def get_all_statuses(self) -> Dict[str, str]:
        """Returns runtime status for each unique registered specialist agent."""
        return {agent.role: agent.get_status() for agent in self._agents.values()}


# ── Global Singleton Instance ────────────────────────────────────────────────
agent_registry = AgentRegistry()

__all__ = [
    "AgentRegistry",
    "agent_registry",
]
