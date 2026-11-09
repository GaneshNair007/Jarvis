"""
JARVIS Core Configuration Substrate.

Provides unified settings access and directly binds the API key rotator
and cloud gateway configurations to the core package.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from jarvis.config import *
from jarvis.config import settings, PROJECT_ROOT
from jarvis.core.api_key_rotator import (
    api_key_rotator,
    gemini_rotator,
    openrouter_rotator,
    nvidia_nim_rotator,
    GeminiKeyRotator,
    OpenRouterKeyRotator,
    NvidiaNimKeyRotator,
)

__all__ = [
    "settings",
    "PROJECT_ROOT",
    "api_key_rotator",
    "gemini_rotator",
    "openrouter_rotator",
    "nvidia_nim_rotator",
    "GeminiKeyRotator",
    "OpenRouterKeyRotator",
    "NvidiaNimKeyRotator",
]
