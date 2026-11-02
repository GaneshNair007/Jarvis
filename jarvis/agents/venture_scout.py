"""
JARVIS Venture Scout & AI Business Idea Matching Engine
Ingests, scores, and creates launch blueprints from the curated catalog of
200 AI Business Ideas (Ayman William Edition).
Tailors monetization, toolkits, and 30-day pilot workflows specifically for
Ganesh Nair's hardware (RTX 4050) and engineering stack (Python, FastAPI, Local ML).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.logger import get_logger
from jarvis.memory.store import db_store

logger = get_logger("agents.venture_scout")


class BusinessIdea(BaseModel):
    idea_id: str
    number: int
    domain: str
    title: str
    target_buyer: str
    problem_statement: str
    solution_statement: str
    how_to_get_started: str
    proof_of_value: str
    revenue_model: str
    sell_this_first: str
    toolkit: str
    lean_startup_budget: str
    scale_ceiling: str
    scale_speed: str
    fit_score: float = 0.0


class VentureScout:
    """
    Evaluates commercial opportunities and scaffolds lean AI businesses.
    """

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or Path(__file__).resolve().parent.parent.parent / "data" / "business_ideas.json"
        self.ideas: List[BusinessIdea] = []
        self._load_ideas()

    def _load_ideas(self) -> None:
        if self.data_path.exists():
            try:
                raw = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.ideas = [BusinessIdea(**item) for item in raw]
                logger.info(f"VentureScout: Loaded {len(self.ideas)} structured AI business ideas.")
            except Exception as e:
                logger.error(f"Failed to load business ideas from {self.data_path}: {e}")
        else:
            logger.warning(f"Business ideas catalog not found at {self.data_path}")

    def search_ideas(
        self,
        query: str = "",
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> List[BusinessIdea]:
        """Filters ideas by search query and domain."""
        q = query.lower().strip()
        matched = []
        for idea in self.ideas:
            if domain and domain.lower() not in idea.domain.lower():
                continue
            searchable = f"{idea.title} {idea.domain} {idea.target_buyer} {idea.problem_statement} {idea.toolkit}".lower()
            if not q or q in searchable:
                matched.append(idea)
        return matched[:limit]

    def match_ideas_for_profile(
        self,
        skills: Optional[List[str]] = None,
        has_gpu: bool = True,
        preferred_domain: Optional[str] = None,
        limit: int = 5,
    ) -> List[BusinessIdea]:
        """
        Calculates a compatibility fit score (0.0 - 1.0) for Ganesh's engineering profile:
        - Stack: Python, FastAPI, Local LLMs, Screen Automation, Kokoro-TTS, React.
        - Hardware: RTX 4050 (6GB VRAM) -> Boosts local speech, vision, and agentic workflows.
        - Cost Constraint: Zero software subscriptions -> Prefers open-source toolkits.
        """
        user_skills = [s.lower() for s in (skills or ["python", "fastapi", "ai agents", "automation", "local llm", "voice"])]
        scored = []

        for idea in self.ideas:
            score = 0.5  # Base score
            text = f"{idea.title} {idea.domain} {idea.solution_statement} {idea.toolkit} {idea.sell_this_first}".lower()

            # Domain preference
            if preferred_domain and preferred_domain.lower() in idea.domain.lower():
                score += 0.2

            # Skill match
            for s in user_skills:
                if s in text:
                    score += 0.08

            # GPU advantage: Edge AI, audio, transcription, automation
            if has_gpu and any(k in text for k in ["voice", "audio", "video", "screen", "transcription", "desktop", "local"]):
                score += 0.15

            # Lean startup budget preference
            if any(b in idea.lean_startup_budget for b in ["₹5,000", "₹10,000", "₹15,000"]):
                score += 0.1

            idea_copy = idea.model_copy()
            idea_copy.fit_score = min(1.0, round(score, 2))
            scored.append(idea_copy)

        scored.sort(key=lambda x: x.fit_score, reverse=True)
        return scored[:limit]

    def generate_launch_blueprint(self, idea_id: str) -> Dict[str, Any]:
        """
        Produces an actionable 30-Day Launch Blueprint for the selected idea.
        """
        idea = next((i for i in self.ideas if i.idea_id.upper() == idea_id.upper() or str(i.number) == idea_id), None)
        if not idea:
            raise ValueError(f"Idea '{idea_id}' not found.")

        milestones = [
            {
                "week": "Week 1: Zero-Cost Asset Creation",
                "action": f"Take 1 sample permissioned case study. Build MVP using {idea.toolkit}.",
                "deliverable": "Working prototype & 5-case test suite.",
            },
            {
                "week": "Week 2: Cold Outreach & Validation",
                "action": f"Contact 10 {idea.target_buyer} prospects with customized demo video/pack.",
                "deliverable": "Secure 2 pilot interview calls.",
            },
            {
                "week": "Week 3: Paid Pilot Deployment",
                "action": f"Deliver {idea.sell_this_first} with manual review step for first client.",
                "deliverable": "Customer sign-off & testimonial.",
            },
            {
                "week": "Week 4: Retainer Conversion & Automation",
                "action": f"Pitch {idea.revenue_model}. Automate repeatable logic using FastAPI + JARVIS agents.",
                "deliverable": "Monthly recurring contract.",
            },
        ]

        blueprint = {
            "idea_id": idea.idea_id,
            "title": idea.title,
            "domain": idea.domain,
            "target_buyer": idea.target_buyer,
            "core_offer": idea.sell_this_first,
            "lean_budget": idea.lean_startup_budget,
            "target_monthly_revenue": idea.revenue_model,
            "idea": idea.model_dump(),
            "milestones": milestones,
            "suggested_toolkit": idea.toolkit,
            "30_day_milestone_plan": milestones,
            "technical_stack_recommendation": {
                "backend": "FastAPI (Python 3.12)",
                "compute": "Local RTX 4050 GPU (Zero Cloud Cost)",
                "database": "SQLite WAL / PostgreSQL",
                "interface": "Next.js / HTML5 HUD Dashboard",
                "orchestrator": "JARVIS Multi-Agent Workforce",
            },
        }

        # Record to memory
        try:
            db_store.save_memory(
                user_id="ganesh",
                text=f"[VENTURE BLUEPRINT] {idea.title}: {idea.sell_this_first} (Target: {idea.target_buyer})",
                category="business_ventures",
                source=f"venture:{idea.idea_id}",
                layer="SEMANTIC",
            )
        except Exception as e:
            logger.warning(f"Could not persist venture blueprint to memory: {e}")

        return blueprint


# Global Singleton Instance
venture_scout = VentureScout()
