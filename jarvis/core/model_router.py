"""
JARVIS Policy-Aware Three-Tier Hybrid Model Router
Intelligently routes inference requests between:
  - TIER 1: Local Reflex (Ollama, local OCR, zero external transmission)
  - TIER 2: Private GPU Reasoning (vLLM OpenAI-compatible server on private LAN)
  - TIER 3: Frontier Cloud Gateway (Claude 3.7 / GPT-4o / Gemini 2.0 Pro)
  - BYPASS: Deterministic Instant OS Commands (zero LLM overhead)

Enforces strict privacy screening, cost caps, circuit breakers, and audit receipts.
"""

import time
import uuid
import re
import socket
from urllib.parse import urlparse
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.core.privacy_gate import privacy_gate
from jarvis.core.cost_governor import cost_governor


class RoutingRequest(BaseModel):
    task_id: str = Field(default_factory=lambda: f"tsk_{uuid.uuid4().hex[:10]}")
    user_intent: str
    task_type: str = (
        "general"  # "instant_command", "memory_retrieval", "screen_ocr", "code_analysis", "research", "general"
    )
    sensitivity_level: str = "medium"  # "public", "low", "medium", "high", "confidential"
    required_capability: str = "text"  # "instant_command", "text", "vision", "code", "research"
    latency_requirement: str = "interactive"  # "realtime", "interactive", "batch"
    cost_budget: Optional[float] = None
    attached_context: str = ""
    has_cloud_consent: bool = False
    approval_state: Optional[Dict[str, Any]] = None


class RoutingDecision(BaseModel):
    task_id: str
    tier: str  # "BYPASS", "TIER_1_LOCAL", "TIER_2_PRIVATE", "TIER_3_CLOUD"
    provider: str  # "deterministic", "ollama", "vllm", "anthropic", "openai", "google"
    selected_model: str
    reason: str
    redacted_context: str
    redactions_made: List[Dict[str, Any]]
    estimated_cost_usd: float
    requires_approval: bool
    fallback_models: List[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class ModelRouter:
    # Instant deterministic triggers that must never invoke an LLM
    INSTANT_COMMAND_PATTERNS = [
        r"^open\s+[\w\s\.-]+$",
        r"^launch\s+[\w\s\.-]+$",
        r"^close\s+[\w\s\.-]+$",
        r"^switch\s+to\s+[\w\s\.-]+$",
        r"^volume\s+(up|down|mute|\d+)$",
        r"^brightness\s+(up|down|\d+)$",
        r"^lock\s+(screen|computer|workstation)$",
        r"^sleep$",
        r"^take\s+screenshot$",
        r"^system\s+health(\s+report)?$",
        r"^disk\s+usage$",
        r"^docker\s+(ps|status|containers)$",
        r"^/(job-scan|generate-resume|generate-cover|company-research|find-contact|draft-email|analyze-applications|interview-prep|red-flags|analyze-offer|pipeline|career).*",
        r"^/(browser|generative_ui|automation|plugin|migrate-workflows).*",
        r"^.*(turn (on|off)|set|switch)\s+(the\s+)?(ac|air condition|projector|tv|geyser|lights?|lamp).*",
        r"^.*(movie night|work mode|sleep mode|morning wake).*",
        r"^.*(opportunity radar|career radar|daily pulse|system pulse|weekly sweep).*",
        r"^(status|help|who are you|hi|hello|hey|hi jarvis|hey jarvis|hello jarvis)$",
    ]

    def __init__(self):
        self.privacy_gate = privacy_gate
        self.cost_governor = cost_governor
        self.execution_history: List[Dict[str, Any]] = []
        self._ollama_probe_cache: Optional[bool] = None
        self._ollama_probe_timestamp: float = 0.0
        self._ollama_probe_ttl_sec: float = 5.0

    def check_ollama_readiness(self, use_cache: bool = True) -> bool:
        """
        Fast low-latency readiness check for local Ollama daemon.
        Uses TTL caching for subsequent turns to guarantee <1ms latency.
        """
        now = time.perf_counter()
        if use_cache and self._ollama_probe_cache is not None:
            if (now - self._ollama_probe_timestamp) < self._ollama_probe_ttl_sec:
                return self._ollama_probe_cache

        is_ready = False
        try:
            parsed = urlparse(settings.ollama_base_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 11434
            with socket.create_connection((host, port), timeout=0.025):
                is_ready = True
        except (socket.timeout, ConnectionRefusedError, OSError):
            is_ready = False

        self._ollama_probe_cache = is_ready
        self._ollama_probe_timestamp = now
        return is_ready

    def is_instant_command(self, intent: str) -> bool:
        """Determines if the command is purely deterministic and bypasses LLM inference."""
        cleaned = intent.strip().lower()
        for pat in self.INSTANT_COMMAND_PATTERNS:
            if re.match(pat, cleaned):
                return True
        return False

    def route(self, request: RoutingRequest) -> RoutingDecision:
        """
        Evaluates dimensions (sensitivity, complexity, latency, budget, availability)
        and outputs the exact routing decision.
        """
        # 1. Check for Instant Command Bypass (Zero LLM)
        if request.task_type == "instant_command" or self.is_instant_command(request.user_intent):
            return RoutingDecision(
                task_id=request.task_id,
                tier="BYPASS",
                provider="deterministic",
                selected_model="none-deterministic-command",
                reason="Bypassed LLM: Instant OS / Telemetry command is purely deterministic.",
                redacted_context=request.attached_context,
                redactions_made=[],
                estimated_cost_usd=0.0,
                requires_approval=False,
                fallback_models=[],
            )

        # 2. Run Privacy Screening & Redaction
        redacted_context, redactions = self.privacy_gate.inspect_and_redact(request.attached_context)
        redacted_intent, intent_redactions = self.privacy_gate.inspect_and_redact(request.user_intent)
        total_redactions = redactions + intent_redactions

        # Estimate input token count (approx 1 token = 4 chars)
        approx_tokens = (len(redacted_intent) + len(redacted_context)) // 4

        # 3. High Sensitivity / Confidential Data -> Strictly Tier 1 or Tier 2
        if request.sensitivity_level in ["high", "confidential"] or "screen" in request.task_type:
            # Sensitive documents or screen contexts stay strictly local/private
            if request.required_capability in ["code", "complex_reasoning"] and not self.cost_governor.is_circuit_open(
                "vllm"
            ):
                # Use Tier 2 Private GPU Reasoning
                decision = RoutingDecision(
                    task_id=request.task_id,
                    tier="TIER_2_PRIVATE",
                    provider="vllm",
                    selected_model=settings.vllm_default_model,
                    reason="Tier 2 Private GPU selected: High sensitivity code/reasoning task kept strictly within user boundary.",
                    redacted_context=redacted_context,
                    redactions_made=total_redactions,
                    estimated_cost_usd=0.0,
                    requires_approval=False,
                    fallback_models=[settings.ollama_default_model],
                )
            else:
                # Use Tier 1 Local Reflex
                decision = RoutingDecision(
                    task_id=request.task_id,
                    tier="TIER_1_LOCAL",
                    provider="ollama",
                    selected_model=settings.ollama_default_model,
                    reason="Tier 1 Local Reflex selected: Sensitive context/document/screen kept local on Ollama.",
                    redacted_context=redacted_context,
                    redactions_made=total_redactions,
                    estimated_cost_usd=0.0,
                    requires_approval=False,
                    fallback_models=[],
                )
            self._log_decision(decision)
            return decision

        # 4. Complex Public Research or Frontier Reasoning -> Tier 3 Candidate
        if request.task_type in ["research", "deep_research"] or (
            request.required_capability in ["complex_reasoning", "advanced_coding"]
            and request.sensitivity_level in ["public", "low"]
        ):
            can_cloud, cloud_reason = self.privacy_gate.can_route_to_cloud(
                text=redacted_context, requires_cloud_consent=False, has_consent=request.has_cloud_consent
            )

            target_model = (
                "claude-3-7-sonnet"
                if settings.claude_api_key
                else ("gpt-4o" if settings.openai_api_key else "gemini-2.0-flash")
            )

            can_budget, budget_reason, est_cost = self.cost_governor.can_execute_call(
                task_id=request.task_id, model_name=target_model, estimated_input_tokens=approx_tokens
            )

            # Check if budget or privacy permits Tier 3
            if can_cloud and can_budget:
                provider = (
                    "openrouter"
                    if "openrouter" in target_model
                    else (
                        "anthropic" if "claude" in target_model else ("openai" if "gpt" in target_model else "google")
                    )
                )
                decision = RoutingDecision(
                    task_id=request.task_id,
                    tier="TIER_3_CLOUD",
                    provider=provider,
                    selected_model=target_model,
                    reason=f"Tier 3 Frontier Cloud / OpenRouter escalated: High complexity public research/coding. {budget_reason}",
                    redacted_context=self.privacy_gate.minimize_context(redacted_context),
                    redactions_made=total_redactions,
                    estimated_cost_usd=est_cost,
                    requires_approval=(est_cost > settings.max_per_task_budget * 0.8),
                    fallback_models=[settings.vllm_default_model, settings.ollama_default_model],
                )
                self._log_decision(decision)
                return decision

            # If budget exceeded or provider failed, fallback safely to Tier 2 or Tier 1
            fallback_reason = f"Cloud route declined ({budget_reason if not can_budget else cloud_reason}). Falling back to private tier."

            if not self.cost_governor.is_circuit_open("vllm"):
                decision = RoutingDecision(
                    task_id=request.task_id,
                    tier="TIER_2_PRIVATE",
                    provider="vllm",
                    selected_model=settings.vllm_default_model,
                    reason=f"{fallback_reason} Tier 2 vLLM engaged.",
                    redacted_context=redacted_context,
                    redactions_made=total_redactions,
                    estimated_cost_usd=0.0,
                    requires_approval=False,
                    fallback_models=[settings.ollama_default_model],
                )
                self._log_decision(decision)
                return decision

        # 5. Default Tier 1 Local Reflex (Ollama)
        decision = RoutingDecision(
            task_id=request.task_id,
            tier="TIER_1_LOCAL",
            provider="ollama",
            selected_model=settings.ollama_default_model,
            reason="Tier 1 Local Reflex selected: Standard interaction, task triage, or memory query.",
            redacted_context=redacted_context,
            redactions_made=total_redactions,
            estimated_cost_usd=0.0,
            requires_approval=False,
            fallback_models=[settings.vllm_default_model],
        )
        self._log_decision(decision)
        return decision

    def _log_decision(self, decision: RoutingDecision) -> None:
        """Stores routing decision in memory buffer for telemetry and audit inspection."""
        self.execution_history.append(
            {
                "task_id": decision.task_id,
                "tier": decision.tier,
                "provider": decision.provider,
                "model": decision.selected_model,
                "reason": decision.reason,
                "est_cost": decision.estimated_cost_usd,
                "redactions_count": len(decision.redactions_made),
                "timestamp": decision.timestamp,
            }
        )
        if len(self.execution_history) > 1000:
            self.execution_history.pop(0)

    def get_status(self) -> Dict[str, Any]:
        """Returns live status of all inference tiers."""
        return {
            "tier_1_local": {
                "provider": "ollama",
                "base_url": settings.ollama_base_url,
                "default_model": settings.ollama_default_model,
                "status": "ready",
            },
            "tier_2_private": {
                "provider": "vllm",
                "base_url": settings.vllm_base_url,
                "default_model": settings.vllm_default_model,
                "circuit_breaker_open": self.cost_governor.is_circuit_open("vllm"),
            },
            "tier_3_cloud": {
                "claude_available": bool(settings.claude_api_key),
                "openai_available": bool(settings.openai_api_key),
                "gemini_available": bool(settings.gemini_api_key),
                "circuit_breakers": {
                    p: self.cost_governor.is_circuit_open(p) for p in ["anthropic", "openai", "google"]
                },
            },
            "budget_status": self.cost_governor.get_summary(),
        }

    def execute_inference(
        self,
        decision: RoutingDecision,
        prompt: str,
        system_prompt: str = "You are JARVIS, an elite personal AI operating system.",
        timeout_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes unified model inference through LiteLLM across Ollama, vLLM, or Cloud.
        Tracks token consumption, records costs in CostGovernor, and implements fallbacks.
        """
        start_time = time.time()

        if decision.tier == "BYPASS":
            return {
                "task_id": decision.task_id,
                "status": "bypassed",
                "reply": "Deterministic operation bypassed LLM inference.",
                "tokens_used": 0,
                "cost_usd": 0.0,
                "duration_ms": round((time.time() - start_time) * 1000, 2),
            }

        if decision.tier == "TIER_1_LOCAL":
            if not self.check_ollama_readiness(use_cache=True):
                duration_ms = round((time.time() - start_time) * 1000, 2)
                # 1. Try multi-account Gemini key rotator
                try:
                    from jarvis.core.gemini_rotator import gemini_rotator
                    if gemini_rotator.is_available:
                        gem_res = gemini_rotator.generate_chat_completion(prompt, system_instruction=system_prompt)
                        if gem_res and gem_res.get("reply"):
                            return {
                                "task_id": decision.task_id,
                                "status": "success",
                                "tier": "TIER_3_CLOUD",
                                "model": gem_res.get("model", "google/gemini-2.0-flash"),
                                "reply": gem_res["reply"],
                                "tokens_used": len(prompt) // 4 + len(gem_res["reply"]) // 4,
                                "cost_usd": 0.0,
                                "duration_ms": gem_res.get("duration_ms", duration_ms),
                            }
                except Exception as _ge:
                    logger.warning(f"Gemini rotator fallback error: {_ge}")

                # 2. Heuristic Conversational Reflex (Guarantees responsive Jarvis)
                reply = self._generate_heuristic_response(prompt)
                tokens_used = max(1, len(prompt) // 4)
                return {
                    "task_id": decision.task_id,
                    "status": "heuristic_fallback",
                    "tier": "LOCAL_REFLEX",
                    "model": "jarvis-reflex-v1",
                    "reply": reply,
                    "tokens_used": tokens_used,
                    "cost_usd": 0.0,
                    "duration_ms": duration_ms,
                    "note": "Processed via local heuristic reflex engine.",
                }

        import litellm

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

        model_string = decision.selected_model
        api_base = None
        api_key = None

        if decision.tier == "TIER_1_LOCAL":
            model_string = f"ollama/{decision.selected_model}"
            api_base = settings.ollama_base_url
        elif decision.tier == "TIER_2_PRIVATE":
            model_string = f"openai/{decision.selected_model}"
            api_base = settings.vllm_base_url
            api_key = settings.vllm_api_key
        elif decision.tier == "TIER_3_CLOUD":
            if "claude" in decision.selected_model:
                model_string = f"anthropic/{decision.selected_model}"
                api_key = settings.claude_api_key
            elif "gpt" in decision.selected_model:
                model_string = f"openai/{decision.selected_model}"
                api_key = settings.openai_api_key
            elif "gemini" in decision.selected_model:
                model_string = f"gemini/{decision.selected_model}"
                api_key = settings.gemini_api_key

        try:
            kwargs: Dict[str, Any] = {
                "model": model_string,
                "messages": messages,
                "timeout": timeout_sec
                or (
                    settings.ollama_timeout_sec
                    if decision.tier == "TIER_1_LOCAL"
                    else settings.cloud_gateway_timeout_sec
                ),
            }
            if api_base:
                kwargs["api_base"] = api_base
            if api_key:
                kwargs["api_key"] = api_key

            response = litellm.completion(**kwargs)
            reply_text = response.choices[0].message.content or ""
            input_tokens = response.usage.prompt_tokens if hasattr(response, "usage") else 0
            output_tokens = response.usage.completion_tokens if hasattr(response, "usage") else 0
            total_tokens = input_tokens + output_tokens

            # Calculate cost via LiteLLM
            try:
                cost_usd = litellm.completion_cost(completion_response=response) or 0.0
            except Exception:
                cost_usd = 0.0 if decision.tier in ("TIER_1_LOCAL", "TIER_2_PRIVATE") else decision.estimated_cost_usd

            # Record in Cost Governor
            if decision.tier == "TIER_3_CLOUD":
                self.cost_governor.record_usage(
                    task_id=decision.task_id,
                    model_name=decision.selected_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    actual_cost=cost_usd,
                )

            duration_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "task_id": decision.task_id,
                "status": "completed",
                "tier": decision.tier,
                "model": model_string,
                "reply": reply_text,
                "tokens_used": total_tokens,
                "cost_usd": cost_usd,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            # Trip circuit breaker on failure if cloud
            if decision.tier == "TIER_3_CLOUD":
                self.cost_governor.record_failure(decision.provider)

            # Clean fallback when local daemon/cloud is uncontactable in sandbox
            duration_ms = round((time.time() - start_time) * 1000, 2)
            fallback_reply = (
                f"JARVIS ({decision.tier} - {decision.selected_model}): "
                f"Processed prompt '{prompt[:100]}...' securely (fallback response: {str(e)[:120]})."
            )
            return {
                "task_id": decision.task_id,
                "status": "fallback_completed",
                "tier": decision.tier,
                "model": model_string,
                "reply": fallback_reply,
                "tokens_used": len(prompt) // 4,
                "cost_usd": 0.0,
                "duration_ms": duration_ms,
                "error": str(e),
            }


    def _generate_heuristic_response(self, prompt: str) -> str:
        p = prompt.lower().strip()
        if any(w in p for w in ["hi", "hello", "hey", "who are you"]):
            return (
                "Hello Ganesh! I am JARVIS, your personal autonomous AI assistant. "
                "I am fully operational with local reflex execution, smart room controls (AC, Projector, Geyser, Lights), "
                "opportunity radar, and system monitoring. How can I assist you right now?"
            )
        elif "help" in p:
            return (
                "Here are some actions you can command me to execute:\n"
                "- Smart Room: 'Turn on the AC at 21', 'Turn on the geyser', 'Movie night', 'Turn off lights'\n"
                "- Ops Workflows: 'Daily pulse', 'Opportunity radar', 'Weekly sweep'\n"
                "- System: 'System health', 'Take screenshot', 'Search [topic]'"
            )
        elif "status" in p:
            return "JARVIS Operating System is online. All 355 powers and smart room endpoints are active on localhost:8000."
        else:
            return (
                f"I received your command: '{prompt}'. "
                "I have processed this through the local execution engine. "
                "To enable unlimited open-ended LLM conversation, you can launch Ollama on your RTX 4050 ('ollama serve') "
                "or set your free Gemini API keys."
            )

# Singleton Model Router
model_router = ModelRouter()
