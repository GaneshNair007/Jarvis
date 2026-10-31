"""JARVIS Multi-Agent Fusion Workers — Planner, Researcher, Executor, Critic."""
from jarvis.agents.swarm import agent_swarm, AgentSwarmCoordinator, AgentRole, SwarmExecutionPlan as AgentPlan, SubTask
from jarvis.agents.planner import PlannerAgent
from jarvis.agents.researcher import ResearcherAgent
from jarvis.agents.executor import ExecutorAgent
from jarvis.agents.critic import CriticAgent

__all__ = [
    "agent_swarm",
    "AgentSwarmCoordinator",
    "AgentRole",
    "AgentPlan",
    "SubTask",
    "PlannerAgent",
    "ResearcherAgent",
    "ExecutorAgent",
    "CriticAgent",
]
