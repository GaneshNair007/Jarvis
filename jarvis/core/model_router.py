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
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.core.privacy_gate import privacy_gate
from jarvis.core.cost_governor import cost_governor

class RoutingRequest(BaseModel):
    task_id: str = Field(default_factory=lambda: f"tsk_{uuid.uuid4().hex[:10]}")
    user_intent: str
    task_type: str = "general" # "instant_command", "memory_retrieval", "screen_ocr", "code_analysis", "research", "general"
    sensitivity_level: str = "medium" # "public", "low", "medium", "high", "confidential"
    required_capability: str = "text" # "instant_command", "text", "vision", "code", "research"
    latency_requirement: str = "interactive" # "realtime", "interactive", "batch"
    cost_budget: Optional[float] = None
    attached_context: str = ""
    has_cloud_consent: bool = False
    approval_state: Optional[Dict[str, Any]] = None

class RoutingDecision(BaseModel):
    task_id: str
    tier: str # "BYPASS", "TIER_1_LOCAL", "TIER_2_PRIVATE", "TIER_3_CLOUD"
    provider: str # "deterministic", "ollama", "vllm", "anthropic", "openai", "google"
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
        r"^docker\s+(ps|status|containers)$"
    ]

    def __init__(self):
        self.privacy_gate = privacy_gate
        self.cost_governor = cost_governor
        self.execution_history: List[Dict[str, Any]] = []

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
                fallback_models=[]
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
            if request.required_capability in ["code", "complex_reasoning"] and not self.cost_governor.is_circuit_open("vllm"):
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
                    fallback_models=[settings.ollama_default_model]
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
                    fallback_models=[]
                )
            self._log_decision(decision)
            return decision

        # 4. Complex Public Research or Frontier Reasoning -> Tier 3 Candidate
        if request.task_type in ["research", "deep_research"] or (
            request.required_capability in ["complex_reasoning", "advanced_coding"]
            and request.sensitivity_level in ["public", "low"]
        ):
            can_cloud, cloud_reason = self.privacy_gate.can_route_to_cloud(
                text=redacted_context,
                requires_cloud_consent=False,
                has_consent=request.has_cloud_consent
            )

            target_model = "claude-3-7-sonnet" if settings.claude_api_key else ("gpt-4o" if settings.openai_api_key else "gemini-2.0-flash")

            can_budget, budget_reason, est_cost = self.cost_governor.can_execute_call(
                task_id=request.task_id,
                model_name=target_model,
                estimated_input_tokens=approx_tokens
            )

            # Check if budget or privacy permits Tier 3
            if can_cloud and can_budget:
                decision = RoutingDecision(
                    task_id=request.task_id,
                    tier="TIER_3_CLOUD",
                    provider="anthropic" if "claude" in target_model else ("openai" if "gpt" in target_model else "google"),
                    selected_model=target_model,
                    reason=f"Tier 3 Frontier Cloud escalated: High complexity public research/coding. {budget_reason}",
                    redacted_context=self.privacy_gate.minimize_context(redacted_context),
                    redactions_made=total_redactions,
                    estimated_cost_usd=est_cost,
                    requires_approval=(est_cost > settings.max_per_task_budget * 0.8),
                    fallback_models=[settings.vllm_default_model, settings.ollama_default_model]
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
                    fallback_models=[settings.ollama_default_model]
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
            fallback_models=[settings.vllm_default_model]
        )
        self._log_decision(decision)
        return decision

    def _log_decision(self, decision: RoutingDecision) -> None:
        """Stores routing decision in memory buffer for telemetry and audit inspection."""
        self.execution_history.append({
            "task_id": decision.task_id,
            "tier": decision.tier,
            "provider": decision.provider,
            "model": decision.selected_model,
            "reason": decision.reason,
            "est_cost": decision.estimated_cost_usd,
            "redactions_count": len(decision.redactions_made),
            "timestamp": decision.timestamp
        })
        if len(self.execution_history) > 1000:
            self.execution_history.pop(0)

    def get_status(self) -> Dict[str, Any]:
        """Returns live status of all inference tiers."""
        return {
            "tier_1_local": {
                "provider": "ollama",
                "base_url": settings.ollama_base_url,
                "default_model": settings.ollama_default_model,
                "status": "ready"
            },
            "tier_2_private": {
                "provider": "vllm",
                "base_url": settings.vllm_base_url,
                "default_model": settings.vllm_default_model,
                "circuit_breaker_open": self.cost_governor.is_circuit_open("vllm")
            },
            "tier_3_cloud": {
                "claude_available": bool(settings.claude_api_key),
                "openai_available": bool(settings.openai_api_key),
                "gemini_available": bool(settings.gemini_api_key),
                "circuit_breakers": {p: self.cost_governor.is_circuit_open(p) for p in ["anthropic", "openai", "google"]}
            },
            "budget_status": self.cost_governor.get_summary()
        }

# Singleton Model Router
model_router = ModelRouter()
