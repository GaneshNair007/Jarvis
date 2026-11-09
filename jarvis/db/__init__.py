"""
JARVIS Database & Operational Brain Package
Implements Domain-Driven Architecture across Models, Repositories, Unit of Work, and Redis State.
"""

from jarvis.db.session import engine, SessionFactory, get_session, init_db, create_test_engine
from jarvis.db.unit_of_work import UnitOfWork
from jarvis.db.events import (
    event_bus,
    BaseEvent,
    TaskCreatedEvent,
    TaskCompletedEvent,
    GoalCompletedEvent,
    OpportunityDiscoveredEvent,
    AgentLifecycleEvent,
)
from jarvis.db.redis_state import redis_state_store, RedisAgentStateStore

__all__ = [
    "engine",
    "SessionFactory",
    "get_session",
    "init_db",
    "create_test_engine",
    "UnitOfWork",
    "event_bus",
    "BaseEvent",
    "TaskCreatedEvent",
    "TaskCompletedEvent",
    "GoalCompletedEvent",
    "OpportunityDiscoveredEvent",
    "AgentLifecycleEvent",
    "redis_state_store",
    "RedisAgentStateStore",
]
