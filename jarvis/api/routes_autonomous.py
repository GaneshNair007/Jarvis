"""
JARVIS Autonomous Routes
Exposes browser, assignments, hackathon, forms
"""
from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
import asyncio

router = APIRouter(prefix="/api/v1/autonomous", tags=["Autonomous"])

@router.post("/browser/init")
async def browser_init(headless: bool = False):
    from jarvis.browser.agent_browser import browser_orchestrator
    result = await browser_orchestrator.initialize(headless=headless)
    return {"status": "ok" if result else "failed", "initialized": result}

@router.post("/browser/navigate")
async def browser_navigate(url: str = Body(..., embed=True)):
    from jarvis.browser.agent_browser import browser_orchestrator
    try:
        result = await browser_orchestrator.navigate(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/assignment/process")
async def process_assignment(subject: str = Body("", embed=True)):
    from jarvis.agents.assignment_agent import assignment_handler
    try:
        result = await assignment_handler.process_assignment(subject=subject)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/assignment/approve")
async def approve_assignment(approval_id: str = Body(..., embed=True)):
    from jarvis.agents.assignment_agent import assignment_handler
    try:
        result = await assignment_handler.approve_and_submit(approval_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/hackathon/run")
async def run_hackathon(auto_execute: bool = True):
    from jarvis.workflows.hackathon_end_to_end import hackathon_pipeline
    try:
        result = await hackathon_pipeline.run_pipeline(auto_execute=auto_execute)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/form/fill")
async def fill_form(url: str = Body(..., embed=True)):
    from jarvis.agents.form_filler_agent import form_filler
    try:
        result = await form_filler.fill_form(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/form/approve")
async def approve_form(approval_id: str = Body(..., embed=True)):
    from jarvis.agents.form_filler_agent import form_filler
    try:
        result = await form_filler.approve(approval_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/multiagent/execute")
async def multiagent_execute(intent: str = Body(..., embed=True)):
    from jarvis.core.multiagent_orchestrator import multiagent_orchestrator
    try:
        goal = await multiagent_orchestrator.create_goal_from_intent(intent)
        graph = await multiagent_orchestrator.decompose_to_dag(goal, intent)
        from jarvis.core.task_executor import TaskExecutor
        executor = TaskExecutor()
        report = await executor.run(graph)
        return {"goal_id": goal.goal_id, "status": report.status.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
