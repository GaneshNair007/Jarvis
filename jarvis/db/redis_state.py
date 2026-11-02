"""
JARVIS Redis Real-Time Agent State Layer
Maintains high-throughput live status, active tasks, and progress telemetry for worker agents.
Gracefully falls back to an in-memory dictionary store if Redis is unavailable locally.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
from typing import Any, Dict, List, Optional
from jarvis.core.logger import get_logger

logger = get_logger("db.redis_state")


class InMemoryStateStore:
    """Thread-safe fallback state store used when Redis server is offline."""

    def __init__(self):
        self._store: Dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            return self._store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        with self._lock:
            self._store[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def keys(self, pattern: str = "*") -> List[str]:
        with self._lock:
            if pattern == "*" or pattern == "agent:*":
                return list(self._store.keys())
            import fnmatch
            return fnmatch.filter(list(self._store.keys()), pattern)


class RedisAgentStateStore:
    """
    Manages live agent status, progress, and heartbeats.
    Key pattern: agent:{department}:{agent_name}:status
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.environ.get("JARVIS_REDIS_URL", "redis://localhost:6379/0")
        self.client = None
        self._fallback_store = InMemoryStateStore()
        self._use_fallback = False
        self._connect()

    def _connect(self) -> None:
        try:
            import redis
            client = redis.from_url(self.redis_url, decode_responses=True, socket_timeout=1.0)
            client.ping()
            self.client = client
            self._use_fallback = False
            logger.info(f"Connected successfully to Redis at {self.redis_url}")
        except Exception as e:
            logger.info(f"Redis not available ({e}); using thread-safe in-memory state fallback.")
            self._use_fallback = True

    def set_agent_status(
        self,
        department: str,
        agent_name: str,
        status: str,
        current_task: Optional[str] = None,
        progress: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Updates live agent state in Redis."""
        key = f"agent:{department.lower()}:{agent_name.lower()}:status"
        payload = {
            "department": department,
            "agent_name": agent_name,
            "status": status,
            "current_task": current_task or "idle",
            "progress": max(0, min(100, progress)),
            "last_heartbeat": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        val = json.dumps(payload)

        if not self._use_fallback and self.client:
            try:
                self.client.set(key, val, ex=86400)
            except Exception:
                self._fallback_store.set(key, val)
        else:
            self._fallback_store.set(key, val)

        return payload

    def get_agent_status(self, department: str, agent_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves real-time status of specified agent."""
        key = f"agent:{department.lower()}:{agent_name.lower()}:status"
        raw = None
        if not self._use_fallback and self.client:
            try:
                raw = self.client.get(key)
            except Exception:
                raw = self._fallback_store.get(key)
        else:
            raw = self._fallback_store.get(key)

        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    def list_active_agents(self) -> List[Dict[str, Any]]:
        """Returns list of all active agents with live status."""
        pattern = "agent:*"
        keys = []
        if not self._use_fallback and self.client:
            try:
                keys = self.client.keys(pattern)
            except Exception:
                keys = self._fallback_store.keys(pattern)
        else:
            keys = self._fallback_store.keys(pattern)

        active = []
        for k in keys:
            if not self._use_fallback and self.client:
                try:
                    raw = self.client.get(k)
                except Exception:
                    raw = self._fallback_store.get(k)
            else:
                raw = self._fallback_store.get(k)

            if raw:
                try:
                    data = json.loads(raw)
                    active.append(data)
                except Exception:
                    continue
        return active

    def clear(self) -> None:
        """Clears state store (useful for test resets)."""
        self._fallback_store = InMemoryStateStore()
        if not self._use_fallback and self.client:
            try:
                keys = self.client.keys("agent:*")
                if keys:
                    self.client.delete(*keys)
            except Exception:
                pass


# Global Singleton Redis State Store
redis_state_store = RedisAgentStateStore()
