"""
JARVIS OpenRouter Free LLM Integration
Provides seamless, zero-cost access to OpenRouter's free router (openrouter/free)
and 19+ zero-cost models (Gemma, Nemotron, LFM, Laguna, Cohere, etc.)
with deep reasoning token extraction, dry-run safety, and fallback recovery.
"""

from typing import Dict, Any, List, Optional
from integrations.base.base_integration import BaseIntegration
from integrations.base.integration_health import IntegrationStatus, HealthReport
from integrations.base.credential_manager import credential_manager
from integrations.openrouter.client import OpenRouterClient, openrouter_client


class OpenRouterIntegration(BaseIntegration):
    """Zero-cost and reasoning model integration powered by OpenRouter."""

    def __init__(self, client: Optional[OpenRouterClient] = None):
        super().__init__(
            integration_id="openrouter",
            display_name="OpenRouter Free AI Gateway",
            category="AI_Model_Gateway",
            description="Zero-cost LLM routing to openrouter/free and 19+ free models with deep reasoning token inspection.",
            required_credentials=["OPENROUTER_API_KEY"],
            required_scopes=["chat:completions"],
            danger_level="low",
            default_approval_tier=0,  # Inference is read-only / Tier 0 Observe
            rate_limit_rpm=60,
            cost_model="free",
            data_sensitivity="medium",
            documentation_url="https://openrouter.ai/openrouter/free",
        )
        self.client = client or openrouter_client

    def connect(self, credentials: Optional[Dict[str, str]] = None) -> bool:
        if credentials:
            for k, v in credentials.items():
                credential_manager.set_override(k, v)
                if k == "OPENROUTER_API_KEY":
                    self.client.api_key = v

        is_valid, _ = credential_manager.validate_credentials(self.required_credentials)
        self.connected = is_valid
        status = "SUCCESS" if is_valid else "FAILED_MISSING_CREDENTIALS"
        self._record_audit("CONNECT", {"connected": self.connected}, status)
        return self.connected

    def disconnect(self) -> bool:
        self.connected = False
        self._record_audit("DISCONNECT", {}, "SUCCESS")
        return True

    def health_check(self) -> HealthReport:
        if self.kill_switched:
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.KILL_SWITCHED,
                connected=self.connected,
                enabled=self.enabled,
                kill_switched=True,
                errors=["Kill switch active for OpenRouter."],
            )

        is_valid, missing = credential_manager.validate_credentials(self.required_credentials)
        if not is_valid:
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.DEGRADED,
                connected=False,
                enabled=self.enabled,
                kill_switched=False,
                errors=[f"Missing credentials: {', '.join(missing)}"],
            )

        return HealthReport(
            integration_id=self.integration_id,
            status=IntegrationStatus.HEALTHY if self.connected else IntegrationStatus.DISCONNECTED,
            connected=self.connected,
            enabled=self.enabled,
            kill_switched=False,
            details={"default_model": self.client.default_model, "base_url": self.client.base_url},
        )

    def _execute_power_impl(self, power_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Concrete execution of OpenRouter power actions."""
        power_key = power_id.lower()
        if power_key.startswith("openrouter."):
            action = power_key[len("openrouter."):]
        else:
            action = power_key

        if action in ("chat", "completion"):
            messages = params.get("messages", [])
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            model = params.get("model", self.client.default_model)
            res = self.client.chat_completion(messages=messages, model=model)
            return {
                "id": res.id,
                "model": res.model,
                "provider": res.provider,
                "content": res.content,
                "reasoning": res.reasoning,
                "reasoning_tokens": res.usage.reasoning_tokens,
                "usage": res.usage.model_dump(),
                "fallback_used": res.fallback_used,
            }

        elif action in ("list_free_models", "models"):
            models = self.client.get_free_models(force_refresh=params.get("force_refresh", False))
            return {"free_models": models, "count": len(models)}

        elif action in ("test_reasoning", "strawberry_test"):
            prompt = params.get("prompt", "How many r's are in the word 'strawberry'?")
            res = self.client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=params.get("model", self.client.default_model),
            )
            return {
                "prompt": prompt,
                "response": res.content,
                "reasoning": res.reasoning,
                "reasoning_tokens": res.usage.reasoning_tokens,
                "model": res.model,
                "provider": res.provider,
                "cost_usd": res.usage.cost,
            }

        else:
            raise ValueError(f"Unknown OpenRouter power action: '{action}'")

    def list_powers(self) -> List[Dict[str, Any]]:
        return [
            {
                "power_id": "openrouter.chat",
                "name": "OpenRouter Free Chat Completion",
                "description": "Executes free LLM chat completion with reasoning token extraction and automatic rate-limit failover.",
                "tier": 0,
                "approval_required": False,
                "danger_level": "low",
            },
            {
                "power_id": "openrouter.list_free_models",
                "name": "List OpenRouter Zero-Cost Models",
                "description": "Lists all 19+ active free models in the OpenRouter ecosystem.",
                "tier": 0,
                "approval_required": False,
                "danger_level": "low",
            },
            {
                "power_id": "openrouter.test_reasoning",
                "name": "Benchmark Reasoning Model",
                "description": "Runs reasoning prompts (e.g., strawberry letter counting) and parses reasoning traces.",
                "tier": 0,
                "approval_required": False,
                "danger_level": "low",
            },
        ]
