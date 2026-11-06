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
    fourth_law_compliant: bool = True  # Fourth Law: reflection record persisted before COMPLETED
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
        """Default agent simulation/execution if no custom handler is provided."""
        await asyncio.sleep(0.01)  # Minimal async yield
        return {
            "task_id": task.task_id,
            "status": "success",
            "summary": f"Executed '{task.name}' successfully via agent '{task.assigned_agent}'.",
            "department": task.department,
            "context_inputs_count": len(context),
            "tools_used": task.tool_requirements or ["default_executor"],
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

        # Post-Goal Reflection (FOURTH LAW: NO MEMORY WITHOUT REFLECTION)
        reflection = self.reflection_engine.reflect_on_goal(graph)

        # Compute summary
        completed = sum(1 for n in graph.nodes.values() if n.status == TaskStatus.COMPLETED)
        failed = sum(1 for n in graph.nodes.values() if n.status == TaskStatus.FAILED)
        cancelled = sum(1 for n in graph.nodes.values() if n.status == TaskStatus.CANCELLED)

        # Fourth Law completion gate (constitution §2, §10.5):
        # a goal may only be declared COMPLETED once a substantive reflection
        # record (lessons/failures/successes/gaps) exists in permanent storage.
        all_tasks_done = completed == len(graph.nodes) and len(graph.nodes) > 0
        reflection_record = self.reflection_engine.get_reflection(graph.goal_id)
        fourth_law_ok = bool(reflection_record) if all_tasks_done else True
        if all_tasks_done and not fourth_law_ok:
            logger.error(
                f"FOURTH LAW VIOLATION: Goal '{graph.goal_id}' finished all tasks but no "
                "reflection record was persisted. Goal marked INCOMPLETE, not COMPLETED."
            )
            overall_status = TaskStatus.INCOMPLETE
        else:
            overall_status = TaskStatus.COMPLETED if all_tasks_done else TaskStatus.FAILED

        report = ExecutionReport(
            goal_id=graph.goal_id,
            status=overall_status,
            total_tasks=len(graph.nodes),
            completed_tasks=completed,
            failed_tasks=failed,
            cancelled_tasks=cancelled,
            duration_seconds=duration,
            reflection=reflection,
            fourth_law_compliant=fourth_law_ok,
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

