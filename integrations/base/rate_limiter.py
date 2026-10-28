"""
JARVIS Integration Rate Limiter
Implements token-bucket sliding window rate limiting per integration.
Prevents API ban, 429 throttling, and runaway automation.
"""

import time
from typing import Dict, Tuple, Any

class IntegrationRateLimiter:
    """Sliding-window token bucket limiter per integration."""

    def __init__(self, default_rpm: int = 60):
        self.default_rpm = default_rpm
        # Map: integration_id -> list of request timestamps
        self._history: Dict[str, list[float]] = {}
        # Map: integration_id -> custom RPM override
        self._limits: Dict[str, int] = {}

    def set_limit(self, integration_id: str, requests_per_minute: int) -> None:
        """Sets custom RPM for a specific integration."""
        self._limits[integration_id] = max(1, requests_per_minute)

    def get_limit(self, integration_id: str) -> int:
        return self._limits.get(integration_id, self.default_rpm)

    def check_rate_limit(self, integration_id: str) -> Tuple[bool, float]:
        """
        Evaluates whether a call can proceed immediately.
        Returns:
            (allowed: bool, wait_seconds: float)
        """
        now = time.time()
        window_start = now - 60.0
        rpm = self.get_limit(integration_id)

        history = self._history.setdefault(integration_id, [])
        # Prune calls older than 60 seconds
        self._history[integration_id] = [t for t in history if t > window_start]
        valid_calls = self._history[integration_id]

        if len(valid_calls) < rpm:
            return True, 0.0

        # Calculate time until the oldest call in the window falls outside
        oldest = valid_calls[0]
        wait_sec = round(max(0.0, 60.0 - (now - oldest)), 2)
        return False, wait_sec

    def record_call(self, integration_id: str) -> bool:
        """
        Records an execution.
        Returns True if call was within limit and recorded; False if blocked.
        """
        allowed, wait_sec = self.check_rate_limit(integration_id)
        if allowed:
            self._history[integration_id].append(time.time())
            return True
        return False

    def reset(self, integration_id: str) -> None:
        """Resets call history for an integration."""
        self._history[integration_id] = []

    def get_status(self, integration_id: str) -> Dict[str, Any]:
        """Returns live utilization telemetry."""
        now = time.time()
        window_start = now - 60.0
        rpm = self.get_limit(integration_id)
        current_calls = len([t for t in self._history.get(integration_id, []) if t > window_start])

        return {
            "integration_id": integration_id,
            "limit_rpm": rpm,
            "current_rpm": current_calls,
            "utilization_percent": round((current_calls / rpm) * 100, 1),
            "remaining_calls": max(0, rpm - current_calls)
        }

# Global rate limiter instance
rate_limiter = IntegrationRateLimiter()
