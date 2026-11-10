"""JARVIS Real-Time Execution Event Bus and Telemetry Contracts.

Emits and broadcasts genuine execution lifecycle events from Orchestrator and
specialist agents to all connected WebSocket clients and audit logs.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional
from jarvis.core.logger import get_logger

logger = get_logger("core.events")


@dataclass
class ExecutionEvent:
    """Standardized event emitted during task orchestration and agent execution."""

    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    execution_id: str = ""
    conversation_id: str = "default_session"
    task_id: str = ""
    agent_id: str = ""
    agent_role: str = ""  # researcher, engineer, academic_tutor, career, productivity, communication, desktop, reviewer
    event_type: str = "stage_transition"  # task_started, stage_transition, agent_started, agent_tool_invoked, agent_completed, agent_failed, verifying, task_completed, task_failed
    stage: int = 1  # 1 to 6
    stage_name: str = "understand"  # understand, plan, select, execute, verify, consolidate
    status: str = "RUNNING"  # IDLE, AVAILABLE, PLANNING, RUNNING, WAITING_FOR_APPROVAL, VERIFYING, COMPLETED, FAILED, UNAVAILABLE
    timestamp: float = field(default_factory=time.time)
    evidence: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["type"] = "execution_event"
        return d


class EventBroadcaster:
    """Thread-safe and asyncio-safe broadcast bus for real execution events."""

    def __init__(self, max_history: int = 100):
        self._listeners: List[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = []
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history

    def register_listener(self, listener: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def emit(self, event: ExecutionEvent) -> None:
        """Broadcasts an execution event to all registered listeners asynchronously."""
        data = event.to_dict()
        self._history.append(data)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        tasks = []
        for listener in list(self._listeners):
            try:
                tasks.append(asyncio.create_task(listener(data)))
            except Exception as e:
                logger.debug(f"Error dispatching to listener: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def emit_sync(self, event: ExecutionEvent) -> None:
        """Helper to emit an event from sync contexts by scheduling on running loop."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event))
        except RuntimeError:
            pass  # No running loop, event stored in history only
        self._history.append(event.to_dict())
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._history[-limit:]


event_broadcaster = EventBroadcaster()

__all__ = ["ExecutionEvent", "EventBroadcaster", "event_broadcaster"]
