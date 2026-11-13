"""JARVIS Dynamic Power Binder & Tool Schema Generator.

Converts operational powers into OpenAI / Ollama compatible function-calling schemas.
Enforces strict tool-budgeting (max 12 active tools per turn) optimized for
the RTX 4050 (6GB VRAM) local inference profile.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional

from jarvis.core.logger import get_logger
from jarvis.core.audit import audit_ledger
from jarvis.powers import (
    browser_powers,
    calendar_powers,
    email_powers,
    homeassistant_powers,
)

logger = get_logger("core.power_binder")


class PowerBinder:
    """Manages tool registration, dynamic tool selection, and schema generation."""

    def __init__(self, max_concurrent_tools: int = 12):
        self.max_concurrent_tools = max_concurrent_tools
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_powers()

    def register_function(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        category: str,
        keywords: List[str],
        privilege_level: int = 1,
    ) -> None:
        """Registers a Python function as an executable tool with parameter inference."""
        sig = inspect.signature(func)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            # Map type annotations
            param_type = "string"
            if param.annotation is int:
                param_type = "integer"
            elif param.annotation is bool:
                param_type = "boolean"
            elif param.annotation in (dict, Dict[str, Any]):
                param_type = "object"
            elif param.annotation in (list, List[str], List[Any]):
                param_type = "array"

            properties[param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}",
            }
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

        self._tools[name] = {
            "name": name,
            "func": func,
            "schema": schema,
            "category": category,
            "keywords": [kw.lower() for kw in keywords],
            "privilege_level": privilege_level,
        }

    def _register_default_powers(self) -> None:
        """Registers concrete powers for calendar, email, smart home, and browser."""
        # Calendar Powers
        self.register_function(
            name="calendar_get_upcoming",
            func=calendar_powers.get_upcoming_events,
            description="Retrieves upcoming calendar events for the next N days.",
            category="calendar",
            keywords=["calendar", "event", "meeting", "schedule", "upcoming", "today", "tomorrow"],
            privilege_level=1,
        )
        self.register_function(
            name="calendar_add_event",
            func=calendar_powers.add_event,
            description="Adds a new event to the local RFC 5545 calendar.",
            category="calendar",
            keywords=["calendar", "event", "schedule", "add event", "create meeting", "remind me"],
            privilege_level=2,
        )
        self.register_function(
            name="calendar_search",
            func=calendar_powers.search_events,
            description="Searches calendar events by title, description, or location.",
            category="calendar",
            keywords=["calendar", "find event", "search meeting"],
            privilege_level=1,
        )

        # Email Powers
        self.register_function(
            name="email_draft",
            func=email_powers.draft_email,
            description="Composes an RFC 822 email draft and saves it to outbox.",
            category="email",
            keywords=["email", "mail", "draft", "write email", "compose"],
            privilege_level=2,
        )
        self.register_function(
            name="email_send",
            func=email_powers.send_email,
            description="Sends an email draft from outbox (requires Tier-3 cryptographic approval).",
            category="email",
            keywords=["send email", "dispatch email", "outbox send"],
            privilege_level=3,
        )
        self.register_function(
            name="email_list_outbox",
            func=email_powers.list_outbox,
            description="Lists pending email drafts waiting in the outbox.",
            category="email",
            keywords=["outbox", "pending emails", "unsent drafts"],
            privilege_level=1,
        )

        # Gmail Inbox Scan (OAuth when connected; clearly-labelled local fallback otherwise)
        self.register_function(
            name="email_scan_opportunities",
            func=email_powers.scan_inbox_for_opportunities,
            description=(
                "Scans the connected Gmail inbox for internship, hackathon, interview, and opportunity messages. "
                "If Gmail is not connected, returns only the explicitly-labelled local .eml fallback."
            ),
            category="email",
            keywords=[
                "gmail", "inbox", "email", "emails", "mail", "internship",
                "hackathon", "opportunity", "interview", "unread",
            ],
            privilege_level=1,
        )

        # Home Assistant Powers
        self.register_function(
            name="home_get_state",
            func=homeassistant_powers.get_entity_state,
            description="Queries the state and attributes of a smart home device or sensor.",
            category="smarthome",
            keywords=[
                "light",
                "temperature",
                "thermostat",
                "sensor",
                "home assistant",
                "door",
                "lock",
            ],
            privilege_level=1,
        )
        self.register_function(
            name="home_call_service",
            func=homeassistant_powers.call_service,
            description="Calls a Home Assistant service (e.g. turn on light) with readback verification.",
            category="smarthome",
            keywords=["turn on", "turn off", "toggle", "switch", "adjust thermostat", "dim light"],
            privilege_level=2,
        )

        # Browser Powers
        self.register_function(
            name="browser_search",
            func=browser_powers.search_web,
            description="Searches the web and returns ranked deduplicated sources.",
            category="browser",
            keywords=[
                "search", "google", "web", "query", "find", "article", "news",
                "hackathon", "internship", "opportunity", "job", "scholarship", "latest",
            ],
            privilege_level=0,
        )
        self.register_function(
            name="browser_read_url",
            func=browser_powers.read_url,
            description="Navigates to a URL and extracts clean DOM text and links.",
            category="browser",
            keywords=["read", "url", "webpage", "site", "html", "inspect", "link"],
            privilege_level=0,
        )

    def select_tools_for_query(
        self,
        query: str,
        limit: Optional[int] = None,
        max_privilege_level: int = 1,
    ) -> List[Dict[str, Any]]:
        """Select only relevant tools within the caller's privilege ceiling.

        A zero-match query returns no tools; arbitrary tools are never attached
        merely to fill the model's tool budget.
        """
        max_tools = min(limit or self.max_concurrent_tools, self.max_concurrent_tools)
        q_lower = query.lower()

        scored = []
        for name, tool in self._tools.items():
            if int(tool.get("privilege_level", 99)) > max_privilege_level:
                continue

            score = 0
            for keyword in tool["keywords"]:
                if keyword in q_lower:
                    score += 2
            if tool["category"] in q_lower:
                score += 3
            if name.replace("_", " ") in q_lower:
                score += 4

            if score > 0:
                scored.append((score, name, tool))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [item[2]["schema"] for item in scored[:max_tools]]

    @staticmethod
    def _result_succeeded(result: Any) -> bool:
        """Interpret a tool receipt without hiding provider or execution failures."""
        if not isinstance(result, dict):
            return True
        if result.get("success") is False or result.get("error"):
            return False
        status = str(result.get("status", "")).strip().lower()
        return status not in {
            "unavailable",
            "partial",
            "partial_failure",
            "cancelled",
            "error",
            "failed",
            "failure",
            "not_found",
            "not_configured",
            "rejected",
            "failed_verification",
            "security_halt",
        }

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a registered tool only when it fits the default read-only policy."""
        if name not in self._tools:
            return {"success": False, "error": f"Tool '{name}' not found in registry."}

        tool_meta = self._tools[name]
        privilege_level = int(tool_meta.get("privilege_level", 99))
        if privilege_level > 1:
            return {
                "success": False,
                "tool": name,
                "error": "APPROVAL_REQUIRED",
                "message": "This tool can modify state or send data and is not callable from the autonomous read-only tool loop.",
            }

        func = tool_meta["func"]
        try:
            result = func(**arguments)
            succeeded = self._result_succeeded(result)
            audit_ledger.record(
                actor="PowerBinder",
                action=f"EXECUTE_{name.upper()}",
                target=name,
                payload=arguments,
                result="SUCCESS" if succeeded else "FAILURE",
            )
            receipt = {"success": succeeded, "tool": name, "result": result}
            if not succeeded:
                receipt["error"] = (
                    result.get("error") or result.get("message") or "The tool did not complete successfully."
                    if isinstance(result, dict)
                    else "The tool did not complete successfully."
                )
            return receipt
        except Exception as exc:
            logger.error("Error executing tool '%s': %s", name, exc, exc_info=True)
            try:
                audit_ledger.record(
                    actor="PowerBinder",
                    action=f"EXECUTE_{name.upper()}",
                    target=name,
                    payload=arguments,
                    result="FAILURE",
                )
            except Exception:
                logger.exception("Failed to record tool failure for %s", name)
            return {"success": False, "tool": name, "error": str(exc)}


# Global Power Binder singleton
power_binder = PowerBinder()
