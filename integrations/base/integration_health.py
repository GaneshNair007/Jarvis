"""
JARVIS Integration Health Monitor
Standardized status telemetry, health checks, and diagnostics.
"""

import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class IntegrationStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    UNCONFIGURED = "UNCONFIGURED"
    KILL_SWITCHED = "KILL_SWITCHED"
    RATE_LIMITED = "RATE_LIMITED"

class HealthReport(BaseModel):
    integration_id: str
    status: IntegrationStatus
    connected: bool
    enabled: bool
    kill_switched: bool
    latency_ms: float = 0.0
    last_checked: float = Field(default_factory=time.time)
    details: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
