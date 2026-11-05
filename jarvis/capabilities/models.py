"""
Capability Models and Maturity Levels
Levels:
  MISSING
  EXPERIMENTAL
  BASIC
  ADVANCED
  ELITE
"""

from __future__ import annotations

import datetime
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CapabilityLevel(str, Enum):
    MISSING = "MISSING"
    EXPERIMENTAL = "EXPERIMENTAL"
    BASIC = "BASIC"
    ADVANCED = "ADVANCED"
    ELITE = "ELITE"


class CapabilitySchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Unique capability identifier e.g. 'ast_code_mapper'")
    level: CapabilityLevel = CapabilityLevel.EXPERIMENTAL
    category: str = Field(default="general", description="engineering, security, research, operations, career")
    description: str = ""
    required_tools: List[str] = Field(default_factory=list)
    success_rate: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
