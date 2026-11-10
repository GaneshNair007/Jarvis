"""
JARVIS Multi-Agent Fusion Workers & Unified 8 Specialized Agents (Milestone 2)

Specialized Agents:
  - ResearcherAgent: Multi-source web, document, and local memory research
  - EngineerAgent: Python sandbox, test runner, git operations, repo scaffolding
  - AcademicTutorAgent: Conceptual explanations, viva prep, assignment solving
  - CareerAgent: GSoC scouting, hackathons, contribution pitches, profile audit
  - ProductivityAgent: RFC 5545 calendar, upcoming deadlines, task scheduling
  - CommunicationAgent: RFC 822 email drafting, outbox, truthful IMAP scanning
  - DesktopAgent: Dynamic 4-tier app resolution, window tracking, screen capture
  - ReviewerAgent: Independent verification reports, safety/PII scan, critique
"""

# Base & Contracts
from jarvis.agents.base import (
    AgentContext,
    AgentResult,
    AgentTask,
    BaseSpecialistAgent,
)

# Registry
from jarvis.agents.registry import (
    AgentRegistry,
    agent_registry,
)

# 8 Specialized Agents & Singletons
from jarvis.agents.researcher import (
    ResearcherAgent,
    ResearchReport,
    ResearchResult,
    researcher_agent,
)
from jarvis.agents.engineer import (
    EngineerAgent,
    engineer_agent,
)
from jarvis.agents.academic_tutor import (
    AcademicTutorAgent,
    academic_tutor_agent,
)
from jarvis.agents.career_agent import (
    CareerAgent,
    career_agent,
)
from jarvis.agents.productivity_agent import (
    ProductivityAgent,
    productivity_agent,
)
from jarvis.agents.communication_agent import (
    CommunicationAgent,
    communication_agent,
)
from jarvis.agents.desktop_agent import (
    DesktopAgent,
    desktop_agent,
)
from jarvis.agents.reviewer_agent import (
    ReviewerAgent,
    VerificationReport,
    reviewer_agent,
)

# Legacy Exports for Zero Regression
from jarvis.agents.critic import CriticAgent, CriticIssue, CriticReport, Verdict, critic_agent
from jarvis.agents.executor import ExecutorAgent
from jarvis.agents.planner import PlannerAgent
from jarvis.agents.swarm import (
    AgentRole,
    AgentSwarmCoordinator,
    SubTask,
    SwarmExecutionPlan as AgentPlan,
    agent_swarm,
)

__all__ = [
    # Contracts
    "BaseSpecialistAgent",
    "AgentTask",
    "AgentContext",
    "AgentResult",
    "VerificationReport",
    # Registry
    "AgentRegistry",
    "agent_registry",
    # Unified 8 Specialist Agents
    "ResearcherAgent",
    "researcher_agent",
    "ResearchReport",
    "ResearchResult",
    "EngineerAgent",
    "engineer_agent",
    "AcademicTutorAgent",
    "academic_tutor_agent",
    "CareerAgent",
    "career_agent",
    "ProductivityAgent",
    "productivity_agent",
    "CommunicationAgent",
    "communication_agent",
    "DesktopAgent",
    "desktop_agent",
    "ReviewerAgent",
    "reviewer_agent",
    # Legacy Exports
    "CriticAgent",
    "CriticIssue",
    "CriticReport",
    "Verdict",
    "critic_agent",
    "ExecutorAgent",
    "PlannerAgent",
    "AgentSwarmCoordinator",
    "AgentRole",
    "AgentPlan",
    "SubTask",
    "agent_swarm",
]
