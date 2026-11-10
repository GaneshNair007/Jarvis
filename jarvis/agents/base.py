"""
JARVIS Specialist Agent Core Base & Contracts (Milestone 2)
Provides:
  - AgentTask: standard task assignment dataclass
  - AgentContext: runtime execution context dataclass
  - AgentResult: structured execution receipt dataclass
  - BaseSpecialistAgent: abstract base class enforcing permitted tool suites
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import uuid
from typing import Any, Dict, List, Literal, Optional


@dataclass
class AgentTask:
    """Represents a structured unit of work assigned to a specialist agent."""

    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    goal: str = ""
    assigned_role: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[Any] = field(default_factory=list)

    @property
    def role(self) -> str:
        """Alias for assigned_role."""
        return self.assigned_role

    @role.setter
    def role(self, value: str) -> None:
        self.assigned_role = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "assigned_role": self.assigned_role,
            "role": self.assigned_role,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
        }


@dataclass
class AgentContext:
    """Execution context and conversational state passed to specialist agents."""

    conversation_id: str = "default_session"
    user_id: str = "ganesh"
    recent_history: List[Dict[str, str]] = field(default_factory=list)
    attached_data: Dict[str, Any] = field(default_factory=dict)
    memory_context: str = ""

    @property
    def history(self) -> List[Dict[str, str]]:
        """Alias for recent_history."""
        return self.recent_history

    @history.setter
    def history(self, value: List[Dict[str, str]]) -> None:
        self.recent_history = value

    @property
    def metadata(self) -> Dict[str, Any]:
        """Alias for attached_data."""
        return self.attached_data

    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        self.attached_data = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "recent_history": self.recent_history,
            "history": self.recent_history,
            "attached_data": self.attached_data,
            "metadata": self.attached_data,
            "memory_context": self.memory_context,
        }


@dataclass
class AgentResult:
    """Standardized result returned by specialist agents."""

    task_id: str = ""
    agent_name: str = ""
    role: str = ""
    status: Literal["SUCCESS", "FAILED", "PARTIAL", "TOOL_NOT_PERMITTED"] = "SUCCESS"
    output: Any = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    tools_used: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "role": self.role,
            "status": self.status,
            "output": self.output,
            "evidence": self.evidence,
            "tools_used": self.tools_used,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class BaseSpecialistAgent(ABC):
    """
    Abstract base class for all 8 Iron Man JARVIS specialized agents.
    Enforces role identity and declared permitted tool suite boundaries.
    """

    name: str = "BaseSpecialistAgent"
    role: str = "base"
    permitted_tools: List[str] = []

    def validate_tool_permitted(self, tool_name: str) -> bool:
        """Checks whether tool_name is within this agent's permitted suite."""
        return tool_name in self.permitted_tools

    def get_status(self) -> str:
        """Returns agent runtime status: 'idle', 'active', or 'error'."""
        return "idle"

    @abstractmethod
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Executes assigned task using permitted tools only."""
        pass


__all__ = [
    "AgentTask",
    "AgentContext",
    "AgentResult",
    "BaseSpecialistAgent",
]
