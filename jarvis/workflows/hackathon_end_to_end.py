"""
JARVIS Hackathon End-to-End Pipeline
Scout -> Analyze Guidelines -> Prompt Mediator -> Create Repo -> Build with OpenHands/Aider -> Verify -> Prep for Submission
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger
from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus, Priority, Goal
from jarvis.core.task_executor import TaskExecutor
from jarvis.core.model_router import model_router, RoutingRequest

logger = get_logger("workflows.hackathon")


class HackathonPipeline:
    def __init__(self):
        self.artifacts_dir = Path("artifacts/hackathons")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def create_hackathon_goal(self, query: str = "Find best AI hackathon for Ganesh and prepare to build") -> Goal:
        goal = Goal(
            goal_id=f"hack_goal_{int(datetime.utcnow().timestamp())}",
            title="Autonomous Hackathon Pipeline",
            description=query,
            priority=Priority.HIGH,
        )
        return goal

    async def build_graph(self, goal: Goal) -> TaskGraph:
        graph = TaskGraph(goal_id=goal.goal_id)
        tasks = [
            TaskNode(task_id="scout_hackathons", name="Scout Hackathons", description="Find relevant hackathons", department="hackathon", priority=Priority.HIGH, tool_requirements=["web_research"]),
            TaskNode(task_id="analyze_guidelines", name="Analyze Guidelines", description="Read rules and create analysis", department="hackathon", priority=Priority.HIGH, dependencies=["scout_hackathons"], tool_requirements=["url_read"]),
            TaskNode(task_id="prompt_mediator", name="Prompt Mediator", description="Merge research into unified prompt for coding agents", department="hackathon", priority=Priority.HIGH, dependencies=["analyze_guidelines"]),
            TaskNode(task_id="create_repo", name="Create Repo", description="Initialize git repo", department="engineering", priority=Priority.HIGH, dependencies=["prompt_mediator"], tool_requirements=["git"]),
            TaskNode(task_id="build_mvp", name="Build MVP", description="Build with OpenHands/Aider", department="engineering", priority=Priority.HIGH, dependencies=["create_repo"], tool_requirements=["code_generation"]),
            TaskNode(task_id="verify_build", name="Verify Build", description="Run tests/lint", department="engineering", priority=Priority.HIGH, dependencies=["build_mvp"]),
            TaskNode(task_id="submission_prep", name="Submission Prep", description="Prepare submission package (NO AUTO SUBMIT)", department="hackathon", priority=Priority.HIGH, dependencies=["verify_build"]),
        ]
        for t in tasks:
            graph.add_node(t)
        return graph

    async def prompt_mediator(self, guidelines: str, research: str) -> Dict[str, Any]:
        prompt = f"""Act as a Prompt Mediator. Take hackathon guidelines and research, create a UNIFIED prompt for coding agents.
Create:
1. PROBLEM_STATEMENT_ANALYSIS.md
2. ARCHITECTURE.md  
3. UNIFIED_BUILD_PROMPT.md (optimized for Antigravity/OpenCode/Claude)

Guidelines:
{guidelines[:8000]}

Research:
{research[:8000]}"""
        routing_req = RoutingRequest(task_id="mediator", user_intent=prompt, task_type="reasoning")
        decision = model_router.route(routing_req)
        result = await asyncio.to_thread(model_router.execute_inference, decision, prompt)
        content = result.get("reply") or result.get("text") or ""
        # Save artifacts
        for fname in ["PROBLEM_STATEMENT_ANALYSIS.md", "ARCHITECTURE.md", "UNIFIED_BUILD_PROMPT.md"]:
            # Simple split - save full content
            path = self.artifacts_dir / fname
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"# {fname}\n\n{content}\n")
        return {"status": "created", "files": [str(p) for p in self.artifacts_dir.glob("*.md")]}

    async def run_pipeline(self, auto_execute: bool = True):
        goal = await self.create_hackathon_goal()
        graph = await self.build_graph(goal)
        if auto_execute:
            executor = TaskExecutor()
            report = await executor.run(graph)
            return {"goal_id": goal.goal_id, "status": report.status.value, "report": report.model_dump()}
        return {"goal_id": goal.goal_id, "graph_tasks": len(graph.nodes)}


hackathon_pipeline = HackathonPipeline()
