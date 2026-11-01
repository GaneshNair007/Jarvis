"""
JARVIS Fast Intent Router (Jev-Style Decision Engine).

Provides ultra-low latency (<10ms) intent classification and triage across:
  - INSTANT_MACRO: Deterministic local OS controls, direct tool shortcuts.
  - LOCAL_TOOL / MCP: Local Model Context Protocol operations (filesystem, git, memory).
  - GUI_ACTION: Visual grounding & UI-TARS desktop manipulation.
  - CLOUD_REASONING: High-context planning, refactoring, deep research.
  - VOICE_COMMAND: Speech stream handling.
"""

from __future__ import annotations

import re
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from jarvis.core.logger import get_logger

logger = get_logger("core.intent_router")


class IntentCategory(str, Enum):
    INSTANT_MACRO = "instant_macro"
    LOCAL_TOOL = "local_tool"
    GUI_ACTION = "gui_action"
    CLOUD_REASONING = "cloud_reasoning"
    VOICE_COMMAND = "voice_command"


class SubsystemDestination(str, Enum):
    LOCAL_MACRO = "local_macro"
    LOCAL_MCP = "local_mcp"
    GUI_GROUNDING = "gui_grounding"
    CLOUD_ROTATOR = "cloud_rotator"
    VOICE_BUS = "voice_bus"


class IntentTriageResult(BaseModel):
    query: str
    intent_category: IntentCategory
    target_subsystem: SubsystemDestination
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: float
    suggested_action: Optional[str] = None
    requires_confirmation: bool = False


class FastIntentRouter:
    """
    Sub-millisecond triage engine inspired by OpenMausBot's Jev engine.
    Triages incoming queries to the optimal execution layer without cloud latency overhead.
    """

    # 1. Instant deterministic macros (OS shortcuts, volume, app control, system inspection)
    MACRO_PATTERNS: List[Tuple[str, str, bool]] = [
        # (Regex, action_tag, requires_confirmation)
        (r"^(?:open|launch)\s+([a-zA-Z0-9_\-\.\s]+)$", "app_launch", False),
        (r"^(?:close|quit|kill)\s+([a-zA-Z0-9_\-\.\s]+)$", "app_close", True),
        (r"^(?:switch\s+to|focus)\s+([a-zA-Z0-9_\-\.\s]+)$", "app_focus", False),
        (r"^volume\s+(up|down|mute|\d+)$", "volume_control", False),
        (r"^brightness\s+(up|down|\d+)$", "brightness_control", False),
        (r"^(?:lock\s+(?:screen|computer|workstation)|lock)$", "lock_screen", False),
        (r"^(?:sleep|standby)$", "system_sleep", True),
        (r"^(?:take\s+screenshot|screenshot|capture\s+screen)$", "screenshot", False),
        (r"^(?:system\s+health|health\s+report|status)$", "health_report", False),
        (r"^(?:disk\s+usage|disk\s+space)$", "disk_usage", False),
        (r"^(?:docker\s+ps|docker\s+status|containers)$", "docker_status", False),
        (r"^(?:hi|hello|hey|hey\s+jarvis|who\s+are\s+you)$", "greeting", False),
    ]

    # 2. Local MCP Tool patterns (Filesystem, Git, Memory Graph, Sequential Thinking)
    MCP_TOOL_PATTERNS: List[Tuple[str, str, str]] = [
        # (Regex, mcp_server, tool_name)
        (r"^(?:read|cat|view|show\s+file)\s+([^\n\r]+)$", "filesystem", "read_file"),
        (r"^(?:write|save\s+to|append\s+to)\s+([^\n\r]+)$", "filesystem", "write_file"),
        (r"^(?:list\s+(?:directory|files|folder)|dir|ls)\s*([^\n\r]*)$", "filesystem", "list_directory"),
        (r"^(?:git\s+status|git\s+log|git\s+diff|git\s+branch|git\s+commit).*", "git", "git_command"),
        (r"^(?:remember|save\s+to\s+memory|recall|query\s+memory)\s+([^\n\r]+)$", "memory", "memory_store"),
        (r"^(?:think\s+step\s+by\s+step|sequential\s+thinking|decompose\s+problem).*", "sequential-thinking", "sequential_thinking"),
    ]

    # 3. GUI Visual Grounding / UI-TARS action patterns
    GUI_ACTION_PATTERNS: List[Tuple[str, str]] = [
        (r"^(?:click|press|tap)\s+(?:on\s+)?(.+)$", "click_element"),
        (r"^(?:double\s+click|doubleclick)\s+(?:on\s+)?(.+)$", "double_click_element"),
        (r"^(?:right\s+click)\s+(?:on\s+)?(.+)$", "right_click_element"),
        (r"^(?:type|input|enter\s+text)\s+['\"](.+)['\"]\s+(?:in|into|at)\s+(.+)$", "type_in_element"),
        (r"^(?:drag|move)\s+(.+)\s+to\s+(.+)$", "drag_element"),
        (r"^(?:scroll\s+(?:up|down|left|right)).*", "scroll_screen"),
        (r"^gui:\s*(.+)$", "raw_gui_command"),
    ]

    # 4. Cloud Reasoning keywords (complex software engineering, deep architecture, multi-turn synthesis)
    CLOUD_REASONING_KEYWORDS = {
        "architect", "refactor", "synthesize", "design system", "deep research",
        "benchmark analysis", "multi-file", "abstract base class", "trade-off analysis",
        "implement algorithm", "analyze codebase", "comprehensive report", "security audit"
    }

    def __init__(self):
        # Precompile regexes for <0.1ms evaluation
        self._compiled_macros = [
            (re.compile(pattern, re.IGNORECASE), tag, req_confirm)
            for pattern, tag, req_confirm in self.MACRO_PATTERNS
        ]
        self._compiled_mcp = [
            (re.compile(pattern, re.IGNORECASE), srv, tool)
            for pattern, srv, tool in self.MCP_TOOL_PATTERNS
        ]
        self._compiled_gui = [
            (re.compile(pattern, re.IGNORECASE), action)
            for pattern, action in self.GUI_ACTION_PATTERNS
        ]

    def triage(self, query: str, context: Optional[str] = None) -> IntentTriageResult:
        """
        Executes fast multi-branch intent triage in <10ms.
        """
        start = time.perf_counter()
        q = (query or "").strip()
        q_lower = q.lower()

        # 0. Voice input stream marker
        if q.startswith("[voice]") or q.startswith("voice:"):
            duration_ms = round((time.perf_counter() - start) * 1000, 3)
            return IntentTriageResult(
                query=q,
                intent_category=IntentCategory.VOICE_COMMAND,
                target_subsystem=SubsystemDestination.VOICE_BUS,
                confidence=0.98,
                entities={"raw_voice_transcript": q.split(":", 1)[-1].strip()},
                latency_ms=duration_ms,
                suggested_action="process_voice_stream",
                requires_confirmation=False,
            )

        # 1. Deterministic Instant Macros
        for regex, tag, req_confirm in self._compiled_macros:
            match = regex.match(q)
            if match:
                entities = {"action": tag}
                if match.groups():
                    entities["target"] = match.group(1).strip()
                duration_ms = round((time.perf_counter() - start) * 1000, 3)
                return IntentTriageResult(
                    query=q,
                    intent_category=IntentCategory.INSTANT_MACRO,
                    target_subsystem=SubsystemDestination.LOCAL_MACRO,
                    confidence=0.99,
                    entities=entities,
                    latency_ms=duration_ms,
                    suggested_action=tag,
                    requires_confirmation=req_confirm,
                )

        # 2. Local MCP Tools (Filesystem, Git, Memory)
        for regex, srv, tool in self._compiled_mcp:
            match = regex.match(q)
            if match:
                entities = {"mcp_server": srv, "tool": tool}
                if match.groups():
                    entities["argument"] = match.group(1).strip()
                duration_ms = round((time.perf_counter() - start) * 1000, 3)
                return IntentTriageResult(
                    query=q,
                    intent_category=IntentCategory.LOCAL_TOOL,
                    target_subsystem=SubsystemDestination.LOCAL_MCP,
                    confidence=0.95,
                    entities=entities,
                    latency_ms=duration_ms,
                    suggested_action=f"{srv}.{tool}",
                    requires_confirmation=("write" in tool or "commit" in tool),
                )

        # 3. GUI Visual Grounding / Screen Interaction
        for regex, action in self._compiled_gui:
            match = regex.match(q)
            if match:
                entities = {"gui_action": action, "parameters": match.groups()}
                duration_ms = round((time.perf_counter() - start) * 1000, 3)
                return IntentTriageResult(
                    query=q,
                    intent_category=IntentCategory.GUI_ACTION,
                    target_subsystem=SubsystemDestination.GUI_GROUNDING,
                    confidence=0.92,
                    entities=entities,
                    latency_ms=duration_ms,
                    suggested_action=action,
                    requires_confirmation=False,
                )

        # 4. Cloud Reasoning Check (lengthy prompt or architectural keywords)
        is_cloud_reasoning = (
            len(q.split()) > 35
            or any(kw in q_lower for kw in self.CLOUD_REASONING_KEYWORDS)
            or (context and len(context) > 500)
        )

        if is_cloud_reasoning:
            duration_ms = round((time.perf_counter() - start) * 1000, 3)
            return IntentTriageResult(
                query=q,
                intent_category=IntentCategory.CLOUD_REASONING,
                target_subsystem=SubsystemDestination.CLOUD_ROTATOR,
                confidence=0.88,
                entities={"reasoning_type": "deep_synthesis"},
                latency_ms=duration_ms,
                suggested_action="cloud_rotator_inference",
                requires_confirmation=False,
            )

        # 5. Default Fallback -> Local Tool / Macro execution
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        return IntentTriageResult(
            query=q,
            intent_category=IntentCategory.LOCAL_TOOL,
            target_subsystem=SubsystemDestination.LOCAL_MCP,
            confidence=0.75,
            entities={"query": q},
            latency_ms=duration_ms,
            suggested_action="local_general_triage",
            requires_confirmation=False,
        )


# Global Singleton
intent_router = FastIntentRouter()
