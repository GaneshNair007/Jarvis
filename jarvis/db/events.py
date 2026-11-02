"""
JARVIS Event Publishing & Reactive Event Bus
Allows repositories and services to publish domain events (TaskCreated, TaskCompleted,
GoalCompleted, OpportunityDiscovered, AgentLifecycle) to trigger reactive agent workflows.
"""

from __future__ import annotations

import asyncio
import datetime
import inspect
from typing import Any, Callable, Dict, List, Type
from pydantic import BaseModel, Field

from jarvis.core.logger import get_logger

logger = get_logger("db.events")


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    event_name: str


class TaskCreatedEvent(BaseEvent):
    event_name: str = "task_created"
    task_id: str
    task_name: str
    department: str
    goal_id: str


class TaskCompletedEvent(BaseEvent):
    event_name: str = "task_completed"
    task_id: str
    task_name: str
    department: str
    agent_id: str
    outputs: Dict[str, Any] = Field(default_factory=dict)


class GoalCompletedEvent(BaseEvent):
    event_name: str = "goal_completed"
    goal_id: str
    title: str
    total_tasks: int


class OpportunityDiscoveredEvent(BaseEvent):
    event_name: str = "opportunity_discovered"
    opportunity_id: str
    opportunity_type: str
    title: str
    score: float
    source: str


class AgentLifecycleEvent(BaseEvent):
    event_name: str = "agent_lifecycle"
    agent_id: str
    state: str  # created, paused, resumed, retired
    reason: str


class EventBus:
    """
    In-process asynchronous and synchronous Event Bus.
    Dispatches domain events to subscribed handler agents.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[BaseEvent], Any]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[BaseEvent], Any]) -> None:
        """Registers a handler for a given event name."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.info(f"Subscribed handler '{handler.__name__}' to event '{event_type}'.")

    def publish(self, event: BaseEvent) -> None:
        """Publishes an event to all registered listeners."""
        handlers = self._subscribers.get(event.event_name, [])
        logger.info(f"EventBus publishing '{event.event_name}' to {len(handlers)} subscriber(s).")
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler(event))
                    except RuntimeError:
                        asyncio.run(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error executing event handler '{getattr(handler, '__name__', str(handler))}': {e}")

    def clear(self) -> None:
        """Clears all event subscriptions."""
        self._subscribers.clear()


# Global Singleton Event Bus
event_bus = EventBus()

