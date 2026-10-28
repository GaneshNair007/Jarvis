"""
JARVIS Cost Governor & Budget Controller
Estimates and enforces cost caps on LLM calls per task, day, and month.
Includes circuit breaker functionality to block runaway cloud expenditures.
"""

import time
import datetime
from typing import Dict, Any, Tuple, Optional
from jarvis.config import settings

class CostGovernor:
    # Model pricing per 1K tokens (estimated USD)
    PRICING_TABLE = {
        # Tier 1 & 2 Local (Free compute)
        "ollama": {"input": 0.0, "output": 0.0},
        "vllm": {"input": 0.0, "output": 0.0},

        # Tier 3 Cloud Frontier
        "claude-3-7-sonnet": {"input": 0.003, "output": 0.015},
        "gpt-4o": {"input": 0.0025, "output": 0.010},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
        "gemini-2.0-pro": {"input": 0.00125, "output": 0.005},
        "default_cloud": {"input": 0.003, "output": 0.015}
    }

    def __init__(self):
        self.daily_budget_limit = settings.daily_budget_limit
        self.monthly_budget_limit = settings.monthly_budget_limit
        self.max_per_task_budget = settings.max_per_task_budget

        # Ledger of usage: { "YYYY-MM-DD": float_cost }
        self.daily_usage: Dict[str, float] = {}
        self.task_usage: Dict[str, float] = {}
        self.model_stats: Dict[str, Dict[str, Any]] = {}

        # Circuit breaker state: { provider: { "failures": int, "tripped_until": float } }
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}

    def _today_key(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def _month_key(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m")

    def estimate_call_cost(self, model_name: str, estimated_input_tokens: int, estimated_output_tokens: int = 500) -> float:
        """Calculates expected cost for an inference call in USD."""
        pricing = self.PRICING_TABLE.get(model_name.lower())
        if not pricing:
            for k, v in self.PRICING_TABLE.items():
                if k in model_name.lower():
                    pricing = v
                    break
        if not pricing:
            pricing = self.PRICING_TABLE["default_cloud"] if ("gpt" in model_name or "claude" in model_name or "gemini" in model_name) else self.PRICING_TABLE["ollama"]

        cost = (estimated_input_tokens / 1000.0 * pricing["input"]) + (estimated_output_tokens / 1000.0 * pricing["output"])
        return round(cost, 6)

    def can_execute_call(self, task_id: str, model_name: str, estimated_input_tokens: int) -> Tuple[bool, str, float]:
        """
        Validates if an execution is within budget limits.
        Returns (allowed: bool, reason: str, estimated_cost: float).
        """
        est_cost = self.estimate_call_cost(model_name, estimated_input_tokens)

        # 1. Local models are free
        if est_cost == 0.0:
            return True, "Local execution within budget", 0.0

        # 2. Check Circuit Breaker
        provider = self._get_provider(model_name)
        if self.is_circuit_open(provider):
            return False, f"Circuit breaker open for provider '{provider}' due to consecutive failures", est_cost

        # 3. Check Per-Task Budget
        current_task_cost = self.task_usage.get(task_id, 0.0)
        if current_task_cost + est_cost > self.max_per_task_budget:
            return False, f"Per-task budget limit exceeded (${current_task_cost + est_cost:.3f} > ${self.max_per_task_budget:.2f})", est_cost

        # 4. Check Daily Budget
        today = self._today_key()
        current_daily_cost = self.daily_usage.get(today, 0.0)
        if current_daily_cost + est_cost > self.daily_budget_limit:
            return False, f"Daily cloud budget limit reached (${current_daily_cost + est_cost:.3f} > ${self.daily_budget_limit:.2f})", est_cost

        return True, "Call approved by Cost Governor", est_cost

    def record_usage(self, task_id: str, model_name: str, input_tokens: int, output_tokens: int, actual_cost: Optional[float] = None) -> float:
        """Records token and dollar expenditure in real time."""
        if actual_cost is None:
            actual_cost = self.estimate_call_cost(model_name, input_tokens, output_tokens)

        today = self._today_key()
        self.daily_usage[today] = self.daily_usage.get(today, 0.0) + actual_cost
        self.task_usage[task_id] = self.task_usage.get(task_id, 0.0) + actual_cost

        # Update model stats
        if model_name not in self.model_stats:
            self.model_stats[model_name] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_cost": 0.0}

        st = self.model_stats[model_name]
        st["calls"] += 1
        st["input_tokens"] += input_tokens
        st["output_tokens"] += output_tokens
        st["total_cost"] = round(st["total_cost"] + actual_cost, 6)

        return actual_cost

    def record_failure(self, provider: str) -> None:
        """Increments consecutive failures and trips circuit breaker if threshold is met."""
        if provider not in self.circuit_breakers:
            self.circuit_breakers[provider] = {"failures": 0, "tripped_until": 0.0}

        self.circuit_breakers[provider]["failures"] += 1
        if self.circuit_breakers[provider]["failures"] >= 3:
            # Trip for 60 seconds
            self.circuit_breakers[provider]["tripped_until"] = time.time() + 60.0

    def record_success(self, provider: str) -> None:
        """Resets circuit breaker failure count on successful call."""
        if provider in self.circuit_breakers:
            self.circuit_breakers[provider]["failures"] = 0
            self.circuit_breakers[provider]["tripped_until"] = 0.0

    def is_circuit_open(self, provider: str) -> bool:
        cb = self.circuit_breakers.get(provider)
        if not cb:
            return False
        if time.time() < cb.get("tripped_until", 0.0):
            return True
        return False

    def _get_provider(self, model_name: str) -> str:
        name = model_name.lower()
        if "claude" in name or "anthropic" in name:
            return "anthropic"
        if "gpt" in name or "openai" in name:
            return "openai"
        if "gemini" in name or "google" in name:
            return "google"
        if "vllm" in name:
            return "vllm"
        return "ollama"

    def get_summary(self) -> Dict[str, Any]:
        today = self._today_key()
        return {
            "daily_spent_usd": round(self.daily_usage.get(today, 0.0), 4),
            "daily_limit_usd": self.daily_budget_limit,
            "monthly_limit_usd": self.monthly_budget_limit,
            "max_per_task_limit_usd": self.max_per_task_budget,
            "models": self.model_stats,
            "active_circuit_breakers": {p: cb["tripped_until"] > time.time() for p, cb in self.circuit_breakers.items()}
        }

# Singleton Cost Governor
cost_governor = CostGovernor()
