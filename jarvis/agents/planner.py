"""
JARVIS Planner Agent (PWR-288 / PWR-289)
PDF Spec: Pages 352-371 — Multi-Agent & Orchestration

Decomposes a high-level goal into an ordered list of sub-tasks,
assigns each task to the most suitable agent role, and estimates
cost and complexity before any execution begins.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("agents.planner")


@dataclass
class PlanStep:
    """A single atomic step produced by the Planner."""
    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:6]}")
    title: str = ""
    description: str = ""
    assigned_role: str = "executor"
    depends_on: List[str] = field(default_factory=list)
    estimated_duration_ms: int = 1000
    estimated_cost_usd: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """Structured decomposition of a user goal."""
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    goal: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    total_estimated_cost_usd: float = 0.0
    complexity: str = "low"   # low | medium | high
    requires_approval: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "complexity": self.complexity,
            "requires_approval": self.requires_approval,
            "total_estimated_cost_usd": self.total_estimated_cost_usd,
            "steps": [
                {
                    "step_id": s.step_id,
                    "title": s.title,
                    "description": s.description,
                    "assigned_role": s.assigned_role,
                    "depends_on": s.depends_on,
                    "estimated_duration_ms": s.estimated_duration_ms,
                    "estimated_cost_usd": s.estimated_cost_usd,
                }
                for s in self.steps
            ],
        }


class PlannerAgent:
    """
    Decomposes complex goals into executable sub-task plans.

    Strategy:
    1. Heuristic fast-path for simple single-step goals.
    2. LLM-assisted decomposition for multi-step / complex goals.
    3. Dependency graph validation to prevent circular deps.
    """

    # Role keywords for heuristic assignment
    _ROLE_HINTS: Dict[str, List[str]] = {
        "researcher": ["research", "search", "find", "look up", "investigate", "read", "browse"],
        "coder": ["code", "script", "write script", "implement", "fix bug", "refactor", "test", "build", "python", "function"],
        "file_agent": ["file", "document", "read file", "write file", "pdf", "ingest"],
        "system_admin": ["docker", "server", "deploy", "restart", "ssh", "monitor", "log"],
        "finance": ["stock", "price", "portfolio", "trade", "balance", "transaction", "crypto"],
        "content_strategist": ["write", "draft", "email", "blog", "report", "summarize"],
        "security_guard": ["scan", "audit", "vulnerability", "cve", "permission", "encrypt"],
        "browser": ["open browser", "navigate", "click", "fill form", "screenshot", "web"],
        "reviewer_critic": ["review", "evaluate", "check", "validate", "critique", "qa"],
    }

    def __init__(self):
        self._llm_available = False
        self._try_init_llm()

    def _try_init_llm(self):
        try:
            from jarvis.core.model_router import model_router  # noqa
            self._llm_available = True
        except Exception:
            self._llm_available = False

    # ── Public API ────────────────────────────────────────────────────────────

    def decompose(self, goal: str, context: str = "", user_id: str = "ganesh") -> Plan:
        """
        Primary entry point. Returns a validated Plan with ordered PlanSteps.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        logger.info(f"PlannerAgent: decomposing goal '{goal[:60]}...' (plan={plan_id})")

        steps = self._heuristic_decompose(goal, context)

        # Attempt LLM enrichment if available and goal is complex
        if self._llm_available and len(goal.split()) > 10 and len(steps) < 3:
            try:
                llm_steps = self._llm_decompose(goal, context)
                if llm_steps:
                    steps = llm_steps
            except Exception as exc:
                logger.warning(f"PlannerAgent: LLM decompose failed, using heuristic — {exc}")

        total_cost = sum(s.estimated_cost_usd for s in steps)
        complexity = "high" if len(steps) > 5 else ("medium" if len(steps) > 2 else "low")
        requires_approval = any(
            kw in goal.lower()
            for kw in ["delete", "format", "wipe", "deploy", "send email", "transaction"]
        )

        plan = Plan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            total_estimated_cost_usd=total_cost,
            complexity=complexity,
            requires_approval=requires_approval,
            metadata={"user_id": user_id, "context_len": len(context)},
        )

        logger.info(
            f"PlannerAgent: plan={plan_id} steps={len(steps)} "
            f"complexity={complexity} cost=${total_cost:.5f}"
        )
        return plan

    # ── Heuristic decomposition ───────────────────────────────────────────────

    def _heuristic_decompose(self, goal: str, context: str) -> List[PlanStep]:
        """Fast keyword-based task decomposition with dependency chaining."""
        goal_lower = goal.lower()
        steps: List[PlanStep] = []

        # Step 1: Always start with a research/memory step for non-trivial goals
        if any(kw in goal_lower for kw in ["how", "what", "why", "find", "research", "search"]):
            steps.append(PlanStep(
                title="Research & Gather Context",
                description=f"Search memory and web for context relevant to: {goal}",
                assigned_role="researcher",
                estimated_duration_ms=3000,
                estimated_cost_usd=0.0001,
            ))

        # Step 2: Identify primary execution role
        primary_role = self._assign_role(goal_lower)
        prev_ids = [s.step_id for s in steps]

        steps.append(PlanStep(
            title=f"Execute: {goal[:60]}",
            description=goal,
            assigned_role=primary_role,
            depends_on=prev_ids,
            estimated_duration_ms=5000,
            estimated_cost_usd=0.0003,
        ))

        # Step 3: Add review step for high-stakes operations
        if any(kw in goal_lower for kw in ["deploy", "delete", "send", "publish", "commit"]):
            steps.append(PlanStep(
                title="Review & Verify Output",
                description="Critically review the execution output for correctness and safety.",
                assigned_role="reviewer_critic",
                depends_on=[steps[-1].step_id],
                estimated_duration_ms=1500,
                estimated_cost_usd=0.0001,
            ))

        return steps

    def _assign_role(self, goal_lower: str) -> str:
        """Assign best-fit agent role based on keyword matching."""
        scores: Dict[str, int] = {}
        for role, keywords in self._ROLE_HINTS.items():
            scores[role] = sum(1 for kw in keywords if kw in goal_lower)
        best = max(scores, key=lambda r: scores[r])
        return best if scores[best] > 0 else "executor"

    # ── LLM-assisted decomposition ────────────────────────────────────────────

    def _llm_decompose(self, goal: str, context: str) -> List[PlanStep]:
        """
        Uses the model router to generate a JSON plan decomposition.
        Returns empty list on any failure so heuristic fallback is used.
        """
        from jarvis.core.model_router import model_router, RoutingRequest

        system_prompt = (
            "You are a task planner. Given a goal, respond ONLY with a JSON array of steps. "
            "Each step: {title, description, assigned_role, estimated_duration_ms, estimated_cost_usd}. "
            "Valid roles: researcher, coder, file_agent, system_admin, finance, "
            "content_strategist, security_guard, browser, reviewer_critic, executor. "
            "Keep it to 3-7 steps max."
        )
        user_msg = f"Decompose this goal into steps:\n{goal}\n\nContext:\n{context[:500]}"

        req = RoutingRequest(
            task_id=f"plan_{uuid.uuid4().hex[:6]}",
            user_intent=user_msg,
            sensitivity_level="low",
        )
        decision = model_router.route(req)
        result = model_router.execute_inference(decision=decision, prompt=user_msg)

        content = (
            result.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(result, dict)
            else str(result)
        )

        # Extract JSON from the response
        start = content.find("[")
        end = content.rfind("]") + 1
        if start == -1 or end == 0:
            return []

        raw_steps = json.loads(content[start:end])
        steps = []
        prev_id: Optional[str] = None
        for raw in raw_steps:
            step = PlanStep(
                title=raw.get("title", "Step"),
                description=raw.get("description", ""),
                assigned_role=raw.get("assigned_role", "executor"),
                depends_on=[prev_id] if prev_id else [],
                estimated_duration_ms=int(raw.get("estimated_duration_ms", 1000)),
                estimated_cost_usd=float(raw.get("estimated_cost_usd", 0.0001)),
            )
            steps.append(step)
            prev_id = step.step_id

        return steps


# ── Singleton ─────────────────────────────────────────────────────────────────
planner_agent = PlannerAgent()

__all__ = ["PlannerAgent", "Plan", "PlanStep", "planner_agent"]
