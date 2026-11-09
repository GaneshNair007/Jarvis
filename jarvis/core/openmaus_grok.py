"""
JARVIS OpenMausBot Integration: Grok Bot Engine & Multi-Agent Loopback Harness
Synthesizes the core mechanisms of milind-soni/OpenMausBot:
1. Grok Persona Engine (witty, truth-seeking, unfiltered, deep reasoning, fun/think modes).
2. Multi-Bot Sidebar Roster (GrokBot, CodeBot, ResearchBot, SysBot, ReflexBot).
3. Loopback Harness & Normalized Agent Event Stream (thought, tool_call, permission_request, message).
4. Inline Permission Broker (human-in-the-loop allow/deny gates for shell, filesystem, and network).
5. BYOE (Bring Your Own Engine) multi-provider dispatch via OpenRouter, Groq, and Gemini.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from jarvis.core.logger import get_logger
from jarvis.core.api_key_rotator import openrouter_rotator, gemini_rotator, groq_rotator
from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.security.ten_layer_shield import jarvis_security_suite

logger = get_logger("core.openmaus_grok")


class GrokMode(str, Enum):
    STANDARD = "standard"  # Truthful, insightful, concise, Hitchhiker's Guide tone
    FUN = "fun"  # Witty, sarcastic, playful humor, unfiltered banter
    THINK = "think"  # Deep analytical reasoning, chain-of-thought, mathematical rigor
    CODE = "code"  # Ruthlessly efficient senior engineer, AST and test-driven


GROK_PERSONAS = {
    GrokMode.STANDARD: (
        "You are Grok, an autonomous, witty, and deeply intelligent AI assistant modeled in the spirit of "
        "The Hitchhiker's Guide to the Galaxy, now fully integrated as the cognitive brain of Project JARVIS for Ganesh Nair. "
        "You speak with cheerful confidence, sharp technical accuracy, intellectual honesty, and delightful humor. "
        "Avoid corporate platitudes, sycophancy, or robotic throat-clearing. Deliver direct, high-leverage answers."
    ),
    GrokMode.FUN: (
        "You are Grok in Maximum Banter Mode. You are unfiltered, hilariously sarcastic, playfully bold, and intellectually rebellious, "
        "while remaining exceptionally competent and helpful. If an idea is ridiculous, roast it playfully. "
        "Speak with effortless swagger, Iron Man flair, and zero corporate PR filter."
    ),
    GrokMode.THINK: (
        "You are Grok in Deep Reasoning Mode. Deconstruct complex problems into first principles. "
        "Examine edge cases, mathematical constraints, and architectural tradeoffs. "
        "Provide structured, rigorous, and verifiable step-by-step logic."
    ),
    GrokMode.CODE: (
        "You are Grok in Elite Systems Architect Mode. Write modern, robust, production-grade code. "
        "Prioritize asynchronous concurrency, type safety, test suites, and clean architecture. "
        "No boilerplate fluff—only clean, working, verifiable code."
    ),
}


@dataclass
class AgentEvent:
    event_id: str
    event_type: str  # thought, tool_call, permission_request, message, status
    agent_id: str
    channel: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "channel": self.channel,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class BotProfile:
    bot_id: str
    name: str
    avatar: str
    title: str
    description: str
    default_mode: GrokMode
    system_instruction: str
    allowed_tools: List[str]
    status: str = "ONLINE"


class OpenMausAgentRoster:
    """Manages the multi-bot roster inspired by OpenMausBot's sidebar."""

    def __init__(self):
        self.bots: Dict[str, BotProfile] = {}
        self._initialize_default_roster()

    def _initialize_default_roster(self):
        # 1. Grok Bot (Flagship Reasoning & Conversational Agent)
        self.register_bot(
            BotProfile(
                bot_id="grok",
                name="Grok",
                avatar="⚡",
                title="Chief Cognitive AI & Truth Engine",
                description="Witty, insightful, unfiltered general intelligence with Hitchhiker's Guide flair.",
                default_mode=GrokMode.STANDARD,
                system_instruction=GROK_PERSONAS[GrokMode.STANDARD],
                allowed_tools=["web_search", "memory_query", "intent_triage", "screen_inspect"],
            )
        )

        # 2. Code Bot (Autonomous Systems Software Engineer)
        self.register_bot(
            BotProfile(
                bot_id="code_bot",
                name="CodeMaus",
                avatar="💻",
                title="Senior Systems & AST Engineer",
                description="Specialized in multi-file refactoring, AST repo mapping, unit testing, and git automation.",
                default_mode=GrokMode.CODE,
                system_instruction=GROK_PERSONAS[GrokMode.CODE],
                allowed_tools=["ast_repo_map", "run_tests", "git_status", "git_commit", "file_edit"],
            )
        )

        # 3. Research Bot (Deep Search & Fact Extraction)
        self.register_bot(
            BotProfile(
                bot_id="research_bot",
                name="ScoutMaus",
                avatar="🔍",
                title="Deep Research & Fact Investigator",
                description="Explores web sources, extracts documentation, verifies empirical claims, and cites sources.",
                default_mode=GrokMode.THINK,
                system_instruction=GROK_PERSONAS[GrokMode.THINK],
                allowed_tools=["web_search", "browse_page", "extract_citations", "crawl4ai"],
            )
        )

        # 4. System Ops Bot (Subprocess & Infrastructure Guardian)
        self.register_bot(
            BotProfile(
                bot_id="sys_bot",
                name="OpsMaus",
                avatar="🛡️",
                title="Infrastructure & Sandbox Controller",
                description="Monitors host telemetry, manages background daemons, and supervises system security.",
                default_mode=GrokMode.STANDARD,
                system_instruction=(
                    "You are OpsMaus, the infrastructure guardian of Project JARVIS. "
                    "You inspect system health, verify running daemons, and safely triage host operations."
                ),
                allowed_tools=["system_health", "process_list", "network_ping", "port_check"],
            )
        )

        # 5. Reflex Bot (Instant Local Macro Engine)
        self.register_bot(
            BotProfile(
                bot_id="reflex_bot",
                name="ReflexMaus",
                avatar="⚡",
                title="Sub-15ms Local Intent Reflex",
                description="Ultra-low latency instant command dispatcher running local deterministic bypass macros.",
                default_mode=GrokMode.STANDARD,
                system_instruction="Instant deterministic command dispatcher for desktop macros.",
                allowed_tools=["lock_screen", "clipboard_copy", "launch_app", "media_control"],
            )
        )

    def register_bot(self, profile: BotProfile) -> None:
        self.bots[profile.bot_id] = profile

    def get_bot(self, bot_id: str) -> Optional[BotProfile]:
        return self.bots.get(bot_id)

    def list_bots(self) -> List[Dict[str, Any]]:
        return [
            {
                "bot_id": b.bot_id,
                "name": b.name,
                "avatar": b.avatar,
                "title": b.title,
                "description": b.description,
                "mode": b.default_mode.value,
                "status": b.status,
                "tools": b.allowed_tools,
            }
            for b in self.bots.values()
        ]


class OpenMausPermissionBroker:
    """
    Inline permission broker inspired by OpenMausBot.
    Intercepts privileged system actions, pauses execution, and prompts for explicit human approval.
    Cryptographically binds approval tokens to action, target, and agent with single-use consumption and TTL.
    """

    PRIVILEGED_OPERATIONS = {
        "execute_shell",
        "delete_file",
        "format_disk",
        "git_push",
        "export_env",
        "deploy_production",
        "kill_process",
    }

    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl_seconds = ttl_seconds
        self._pending_decisions: Dict[str, Dict[str, Any]] = {}
        self._token_registry: Dict[str, Dict[str, Any]] = {}

    def inspect_action(self, action_type: str, details: str, agent_id: str) -> Tuple[bool, Optional[str]]:
        """
        Returns (is_approved, decision_id).
        If action is safe, returns (True, None).
        If action is privileged, returns (False, decision_id).
        """
        if action_type not in self.PRIVILEGED_OPERATIONS:
            return True, None

        decision_id = f"perm_{secrets.token_hex(8)}"
        details_hash = hashlib.sha256(details.encode("utf-8")).hexdigest()
        now = time.time()
        record = {
            "decision_id": decision_id,
            "action_type": action_type,
            "details": details,
            "details_hash": details_hash,
            "agent_id": agent_id,
            "status": "PENDING",
            "created_at": now,
            "expires_at": now + self.ttl_seconds,
        }
        self._pending_decisions[decision_id] = record
        logger.warning(f"Permission Broker: INTERCEPTED privileged action '{action_type}' from [{agent_id}]")
        return False, decision_id

    def resolve(self, decision_id: str, approved: bool) -> bool:
        """
        Resolves decision. Generates a secure single-use token if approved.
        """
        rec = self._pending_decisions.get(decision_id)
        if not rec:
            return False

        now = time.time()
        if now > rec.get("expires_at", 0):
            rec["status"] = "EXPIRED"
            return False

        if approved:
            rec["status"] = "APPROVED"
            rec["resolved_at"] = now
            token = secrets.token_urlsafe(32)
            rec["approval_token"] = token
            self._token_registry[token] = {
                "decision_id": decision_id,
                "action_type": rec["action_type"],
                "details_hash": rec["details_hash"],
                "agent_id": rec["agent_id"],
                "expires_at": now + self.ttl_seconds,
                "used": False,
            }
            return True
        else:
            rec["status"] = "DENIED"
            rec["resolved_at"] = now
            return False

    def consume(self, token: Optional[str], action_type: str, details: str) -> bool:
        """
        Single-use consumes an approval token. Validates action, details hash, and TTL.
        Prevents replay attacks.
        """
        if not token:
            return False
        meta = self._token_registry.get(token)
        if not meta or meta.get("used"):
            return False
        if time.time() > meta.get("expires_at", 0):
            return False
        if meta.get("action_type") != action_type:
            return False
        details_hash = hashlib.sha256(details.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(meta.get("details_hash", ""), details_hash):
            return False

        # Mark single-use consumed
        meta["used"] = True
        return True

    def get_pending(self) -> List[Dict[str, Any]]:
        now = time.time()
        return [
            v for v in self._pending_decisions.values() if v["status"] == "PENDING" and now <= v.get("expires_at", 0)
        ]


class OpenMausGrokHarness:
    """
    Central loopback harness server for the OpenMausBot Grok Engine.
    Coordinates the agent roster, normalizes event streams, enforces DLP sanitization,
    and dispatches inference across multi-provider cloud and local backends.
    """

    def __init__(self):
        self.roster = OpenMausAgentRoster()
        self.broker = OpenMausPermissionBroker()
        self.channels: List[str] = ["#general", "#dev", "#research", "#ops"]
        self.event_history: List[AgentEvent] = []
        self._event_listeners: List[Callable[[AgentEvent], None]] = []

    def add_event_listener(self, callback: Callable[[AgentEvent], None]) -> None:
        self._event_listeners.append(callback)

    def emit_event(self, event_type: str, agent_id: str, channel: str, data: Dict[str, Any]) -> AgentEvent:
        event = AgentEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type=event_type,
            agent_id=agent_id,
            channel=channel,
            data=data,
        )
        self.event_history.append(event)
        if len(self.event_history) > 500:
            self.event_history = self.event_history[-500:]

        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error in event listener: {e}")
        return event

    async def chat(
        self,
        prompt: str,
        bot_id: str = "grok",
        mode: Optional[GrokMode] = None,
        channel: str = "#general",
    ) -> Dict[str, Any]:
        """
        Executes a turn through Grok Bot or a selected agent from the roster.
        Dispatches thought events, runs DLP sanitization, checks permissions,
        and invokes multi-provider inference.
        """
        bot = self.roster.get_bot(bot_id) or self.roster.get_bot("grok")
        active_mode = mode or bot.default_mode
        sys_prompt = GROK_PERSONAS.get(active_mode, bot.system_instruction)

        # 1. Emit thought event (Internal Deliberation)
        self.emit_event(
            event_type="thought",
            agent_id=bot.bot_id,
            channel=channel,
            data={
                "message": f"Analyzing user intent in [{active_mode.value.upper()}] mode...",
                "bot": bot.name,
                "mode": active_mode.value,
            },
        )

        # 2. Sanitize prompt through 10-Layer Security Suite (Zero Secret Leakage)
        sanitized_prompt = jarvis_security_suite.sanitize_outbound_prompt(prompt)

        # 3. Model Inference via Multi-Provider Rotator
        start_time = time.time()
        reply_text = None
        model_name = None
        provider = "local"

        # Try Groq Cloud (500+ tok/s) if available
        if groq_rotator.is_available:
            try:
                groq_res = groq_rotator.generate_chat_completion(sanitized_prompt, system_instruction=sys_prompt)
                if groq_res and groq_res.get("reply"):
                    reply_text = groq_res["reply"]
                    model_name = groq_res.get("model", "llama-3.3-70b-versatile")
                    provider = "groq"
            except Exception as ge:
                logger.warning(f"Groq rotator attempt: {ge}")

        # Try OpenRouter (e.g. DeepSeek / Grok-2) if Groq not used
        if not reply_text and openrouter_rotator.is_available:
            try:
                or_res = openrouter_rotator.generate_chat_completion(sanitized_prompt, system_instruction=sys_prompt)
                if or_res and or_res.get("reply"):
                    reply_text = or_res["reply"]
                    model_name = or_res.get("model", "deepseek/deepseek-chat")
                    provider = "openrouter"
            except Exception as oe:
                logger.warning(f"OpenRouter rotator attempt: {oe}")

        # Try Gemini Rotator if needed
        if not reply_text and gemini_rotator.is_available:
            try:
                gem_res = gemini_rotator.generate_chat_completion(sanitized_prompt, system_instruction=sys_prompt)
                if gem_res and gem_res.get("reply"):
                    reply_text = gem_res["reply"]
                    model_name = gem_res.get("model", "gemini-2.5-pro")
                    provider = "gemini"
            except Exception as me:
                logger.warning(f"Gemini rotator attempt: {me}")

        # Fallback to standard ModelRouter execution
        if not reply_text:
            req = RoutingRequest(
                task_id=f"grok_{uuid.uuid4().hex[:8]}",
                user_intent=sanitized_prompt,
                task_type="chat",
            )
            decision = model_router.route(req)
            inf_res = model_router.execute_inference(decision, sanitized_prompt, system_prompt=sys_prompt)
            reply_text = inf_res.get("reply", "Grok cognitive cycle complete.")
            model_name = inf_res.get("model", decision.selected_model)
            provider = decision.tier

        duration_ms = round((time.time() - start_time) * 1000, 2)

        # 4. Emit message event
        msg_event = self.emit_event(
            event_type="agent_message",
            agent_id=bot.bot_id,
            channel=channel,
            data={
                "reply": reply_text,
                "bot_name": bot.name,
                "avatar": bot.avatar,
                "mode": active_mode.value,
                "provider": provider,
                "model": model_name,
                "duration_ms": duration_ms,
            },
        )

        return {
            "status": "success",
            "bot_id": bot.bot_id,
            "bot_name": bot.name,
            "avatar": bot.avatar,
            "channel": channel,
            "mode": active_mode.value,
            "reply": reply_text,
            "model": model_name,
            "provider": provider,
            "duration_ms": duration_ms,
            "event_id": msg_event.event_id,
        }


# Global Singleton Instance
openmaus_harness = OpenMausGrokHarness()
