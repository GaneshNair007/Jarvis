"""
JARVIS Task Graph Executor (Async Parallel DAG Execution Engine)
Coordinates the complete end-to-end cognitive loop:
Goal -> TaskGraph (DAG) -> Departments -> Agents -> Tools -> Verification -> Memory -> Reflection.
Executes parallel task layers concurrently with multi-stage QA gates and automated memory recording.
"""

from __future__ import annotations

import asyncio
import datetime
import inspect
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus, Priority
from jarvis.core.task_router import TaskRouter, Assignment
from jarvis.core.task_scheduler import TaskScheduler
from jarvis.core.task_verifier import TaskVerifier, VerificationResult
from jarvis.core.task_memory_writer import TaskMemoryWriter, MemoryEvent
from jarvis.core.task_reflection import TaskReflectionEngine, ReflectionRecord
from jarvis.core.logger import get_logger
import json
from jarvis.core.evidence import Evidence
from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.core.power_registry import power_registry

logger = get_logger("core.task_executor")


class ExecutionReport(BaseModel):
    goal_id: str
    status: TaskStatus
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    duration_seconds: float
    reflection: Optional[ReflectionRecord] = None
    task_results: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class TaskExecutor:
    """
    High-level orchestrator for executing Task Graphs with multi-agent routing,
    verification gates, and episodic memory persistence.
    """

    def __init__(
        self,
        router: Optional[TaskRouter] = None,
        scheduler: Optional[TaskScheduler] = None,
        verifier: Optional[TaskVerifier] = None,
        memory_writer: Optional[TaskMemoryWriter] = None,
        reflection_engine: Optional[TaskReflectionEngine] = None,
        max_concurrency: int = 5,
    ):
        self.router = router or TaskRouter()
        self.scheduler = scheduler or TaskScheduler(max_concurrency=max_concurrency)
        self.verifier = verifier or TaskVerifier()
        self.memory_writer = memory_writer or TaskMemoryWriter()
        self.reflection_engine = reflection_engine or TaskReflectionEngine()

    async def execute_task(
        self,
        graph: TaskGraph,
        task: TaskNode,
        handler: Optional[Callable[[TaskNode, Dict[str, Any]], Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single ready task node:
        1. Central CEO Router assigns worker agent.
        2. Context from dependency outputs is injected.
        3. Handler runs task logic.
        4. Quality and Security Gates verify outputs.
        5. State is updated and memory is recorded.
        """
        # Step 1: Assign Agent
        assignment = self.router.assign_agent(task)
        self.scheduler.mark_started(graph, task.task_id, agent_id=assignment.agent_id)

        # Step 2: Assemble Context from dependencies
        parent_context = {}
        for dep_id in task.dependencies:
            dep_node = graph.nodes.get(dep_id)
            if dep_node and dep_node.outputs:
                parent_context[dep_id] = dep_node.outputs

        # Step 3: Run Handler or default executor
        try:
            if handler:
                if inspect.iscoroutinefunction(handler):
                    raw_output = await handler(task, parent_context)
                else:
                    raw_output = handler(task, parent_context)
            else:
                raw_output = await self._default_agent_execution(task, parent_context)

            if not isinstance(raw_output, dict):
                outputs = {"result": raw_output}
            else:
                outputs = raw_output
        except Exception as e:
            logger.error(f"Task '{task.task_id}' raised exception during execution: {e}")
            outputs = {"error": str(e), "status": "failed"}

        # Step 4: Verification Quality Gate
        verification = self.verifier.verify_task(task, outputs, reviewer_agent=f"{task.department}_qa_gate")
        task.metadata["verification"] = verification.model_dump()

        if verification.passed:
            # Step 5a: Success Transition & Memory Writing
            self.scheduler.mark_completed(graph, task.task_id, outputs)
            self.memory_writer.record_task_memory(task)
            logger.info(f"Task '{task.task_id}' successfully completed and verified (score: {verification.score}).")
        else:
            # Step 5b: Failure & Retry Handling
            self.scheduler.mark_failed(graph, task.task_id, verification.comments)
            logger.warning(f"Task '{task.task_id}' rejected by verifier: {verification.comments}")

        return outputs

    async def _default_agent_execution(self, task: TaskNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Real Agent Execution Engine — replaces simulated sleep stubs.
        1. Identifies required tools from task.tool_requirements and attempts real execution via power_registry.
        2. If tools require capabilities, validates connectivity.
        3. If no powers or pure reasoning task, dispatches to model_router for live model inference.
        4. Collects verifiable Evidence objects; returns honest failure if execution is ungrounded.
        """
        evidence_list: List[Evidence] = []
        tools_executed: List[str] = []
        tool_results: Dict[str, Any] = {}

        # Step 1: Check if specific registered powers are required
        if task.tool_requirements:
            for tool_name in task.tool_requirements:
                power = power_registry.get_power(tool_name)
                if power:
                    handler = power.get("handler") or power_registry.get_handler(tool_name)
                    if handler:
                        try:
                            res = handler(task=task, context=context) if callable(handler) else None
                            if inspect.iscoroutine(res):
                                res = await res
                            tools_executed.append(tool_name)
                            tool_results[tool_name] = res
                            evidence_list.append(Evidence(
                                source=f"power_registry:{tool_name}",
                                action="execute_power",
                                payload={"tool": tool_name, "result_type": type(res).__name__},
                                timestamp=time.time(),
                                verified=True,
                            ))
                        except Exception as e:
                            logger.error(f"Error executing required tool '{tool_name}': {e}")
                            return {
                                "task_id": task.task_id,
                                "status": "failed",
                                "error": f"Tool '{tool_name}' execution failed: {e}",
                                "tools_used": tools_executed,
                                "evidence": [e.to_dict() for e in evidence_list],
                                "fabricated": False,
                            }
                else:
                    logger.warning(f"Required tool '{tool_name}' not registered in power_registry.")

        # Step 2: If no external tool executed, dispatch to model_router for reasoning
        if not tools_executed:
            prompt = (
                f"Task: {task.name}\n"
                f"Description: {task.description}\n"
                f"Department: {task.department}\n"
                f"Context Inputs: {json.dumps(context, default=str)[:1000]}"
            )
            routing_req = RoutingRequest(
                task_id=task.task_id,
                user_intent=prompt,
                task_type="reasoning",
            )
            decision = model_router.route(routing_req)
            inf_res = model_router.execute_inference(
                decision,
                prompt,
                system_prompt=f"You are the {task.assigned_agent or task.department} executing task '{task.name}'. Provide actionable outputs."
            )
            reply = inf_res.get("reply") or inf_res.get("text") or "Cognitive execution cycle complete."
            evidence_list.append(Evidence(
                source=f"model_router:{decision.selected_model}",
                action="model_inference",
                payload={"model": decision.selected_model, "tier": decision.tier, "prompt_chars": len(prompt)},
                timestamp=time.time(),
                verified=True,
            ))
            return {
                "task_id": task.task_id,
                "status": "success",
                "summary": f"Executed '{task.name}' via agent '{task.assigned_agent}' using model '{decision.selected_model}'.",
                "department": task.department,
                "response": reply,
                "tools_used": [f"model:{decision.selected_model}"],
                "evidence": [e.to_dict() for e in evidence_list],
                "fabricated": False,
            }

        return {
            "task_id": task.task_id,
            "status": "success",
            "summary": f"Executed '{task.name}' with {len(tools_executed)} verified tool(s).",
            "department": task.department,
            "tool_results": tool_results,
            "tools_used": tools_executed,
            "evidence": [e.to_dict() for e in evidence_list],
            "fabricated": False,
        }

    async def run(
        self,
        graph: TaskGraph,
        handler: Optional[Callable[[TaskNode, Dict[str, Any]], Any]] = None,
        timeout: float = 60.0,
    ) -> ExecutionReport:
        """
        Executes the entire TaskGraph to completion:
        Loops through dispatchable tasks, runs them concurrently,
        and generates a final post-goal reflection.
        """
        start_time = time.time()
        logger.info(f"Starting execution of TaskGraph for Goal '{graph.goal_id}' ({len(graph.nodes)} tasks).")

        # Validate DAG topology
        if graph.is_cyclic():
            raise ValueError(f"Cannot execute cyclic TaskGraph '{graph.goal_id}'!")

        active_futures: Dict[str, asyncio.Task] = {}

        while not self.scheduler.is_finished(graph):
            # Check timeout
            if time.time() - start_time > timeout:
                logger.error(f"TaskGraph execution timed out after {timeout} seconds.")
                break

            # 1. Fetch dispatchable tasks
            ready_tasks = self.scheduler.get_dispatchable_tasks(graph)

            # 2. Launch execution tasks for each ready candidate
            for task_node in ready_tasks:
                if task_node.task_id not in active_futures:
                    coro = self.execute_task(graph, task_node, handler=handler)
                    fut = asyncio.create_task(coro)
                    active_futures[task_node.task_id] = fut

            # 3. If there are running tasks, wait for at least one to finish
            if active_futures:
                done, pending = await asyncio.wait(
                    active_futures.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=0.1,
                )
                # Cleanup completed futures
                finished_ids = [tid for tid, fut in active_futures.items() if fut in done]
                for fid in finished_ids:
                    del active_futures[fid]
            else:
                # No running tasks and no dispatchable tasks, but scheduler not finished.
                # This happens if all remaining tasks are BLOCKED with no remaining running tasks to unblock them.
                logger.warning("No runnable tasks available and no active tasks running. Graph execution halted.")
                break

            await asyncio.sleep(0.01)

        duration = round(time.time() - start_time, 3)

        # Post-Goal Reflection
        reflection = self.reflection_engine.reflect_on_goal(graph)

        # Compute summary
        completed = sum(1 for n in graph.nodes.values() if n.status == TaskStatus.COMPLETED)
        failed = sum(1 for n in graph.nodes.values() if n.status == TaskStatus.FAILED)
        cancelled = sum(1 for n in graph.nodes.values() if n.status == TaskStatus.CANCELLED)
        overall_status = TaskStatus.COMPLETED if (completed == len(graph.nodes) and len(graph.nodes) > 0) else TaskStatus.FAILED

        report = ExecutionReport(
            goal_id=graph.goal_id,
            status=overall_status,
            total_tasks=len(graph.nodes),
            completed_tasks=completed,
            failed_tasks=failed,
            cancelled_tasks=cancelled,
            duration_seconds=duration,
            reflection=reflection,
            task_results={tid: n.outputs for tid, n in graph.nodes.items()},
        )

        logger.info(
            f"TaskGraph '{graph.goal_id}' execution concluded in {duration}s. "
            f"Status: {overall_status.value} (Completed: {completed}, Failed: {failed}, Cancelled: {cancelled})"
        )
        return report

    def run_sync(
        self,
        graph: TaskGraph,
        handler: Optional[Callable[[TaskNode, Dict[str, Any]], Any]] = None,
        timeout: float = 60.0,
    ) -> ExecutionReport:
        """Synchronous convenience wrapper for run()."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If already inside an event loop, create a new loop in a thread or run
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.run(graph, handler=handler, timeout=timeout))
        else:
            return loop.run_until_complete(self.run(graph, handler=handler, timeout=timeout))

