"""
JARVIS Prompt Mediator - Mediate between models/agents
Copies prompts, creates research MDs, merges outputs
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from jarvis.core.logger import get_logger
from jarvis.core.model_router import model_router, RoutingRequest

logger = get_logger("agents.prompt_mediator")


class PromptMediator:
    def __init__(self):
        self.out_dir = Path("artifacts/mediated")
        self.out_dir.mkdir(parents=True, exist_ok=True)

    async def mediate(self, problem: str, guidelines: str = "", research: List[str] = None) -> Dict[str, Any]:
        research = research or []
        prompt = f"""You are the PROMPT MEDIATOR. 
Take the hackathon/problem, guidelines, and research. Create:
1. RESEARCH_SYNTHESIS.md - combined research
2. UNIFIED_PROMPT_ANTIGRAVITY.md - optimized for Antigravity
3. UNIFIED_PROMPT_OPENCODE.md - optimized for OpenCode  
4. COMBINED_PROJECT_SPEC.md - merged best approach

Problem:
{problem}

Guidelines:
{guidelines[:6000]}

Research:
{json.dumps(research, indent=2)[:6000]}

Make it actionable. Include architecture, file structure, implementation plan."""
        routing_req = RoutingRequest(task_id=f"med_{datetime.utcnow().timestamp()}", user_intent=prompt, task_type="reasoning")
        decision = model_router.route(routing_req)
        result = await asyncio.to_thread(model_router.execute_inference, decision, prompt)
        content = result.get("reply") or result.get("text") or ""
        for fname in ["RESEARCH_SYNTHESIS.md", "UNIFIED_PROMPT_ANTIGRAVITY.md", "UNIFIED_PROMPT_OPENCODE.md", "COMBINED_PROJECT_SPEC.md"]:
            path = self.out_dir / fname
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"# {fname}\n\n{content}\n")
        return {"status": "mediated", "files": [str(p) for p in self.out_dir.glob("*.md")], "model": decision.selected_model}


prompt_mediator = PromptMediator()
