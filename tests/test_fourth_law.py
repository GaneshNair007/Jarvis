"""
FOURTH LAW TESTS — NO MEMORY WITHOUT REFLECTION (Constitution §2, §10.5)
Amended v1.2.0 of docs/constitution/JARVIS_MASTER_DIRECTIVE.md.

Proves that JARVIS cannot declare a goal COMPLETED unless a substantive
reflection record (lessons / failures / successes / capability gaps) has been
generated and persisted to permanent memory.

  1. Compliance: all tasks done + real reflection engine -> COMPLETED, record persisted.
  2. Adversarial: reflection engine produces no record -> goal marked INCOMPLETE,
     never COMPLETED (no fake success even when every task succeeded).
  3. Adversarial: missing reflection is evidenced on the ExecutionReport
     (fourth_law_compliant=False, reflection=None).
  4. Reflection record contains the four Fourth-Law-mandated sections.
"""

import json
from typing import Any, Dict

import pytest

from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus, Priority
from jarvis.core.task_router import TaskRouter
from jarvis.core.task_scheduler import TaskScheduler
from jarvis.core.task_verifier import TaskVerifier
from jarvis.core.task_memory_writer import TaskMemoryWriter
from jarvis.core.task_reflection import TaskReflectionEngine, ReflectionRecord
from jarvis.core.task_executor import TaskExecutor


def _build_goal_graph(goal_id: str) -> TaskGraph:
    """Two-task DAG whose tasks are all verified and executed successfully."""
    graph = TaskGraph(goal_id=goal_id)
    t1 = TaskNode(
        task_id="t1",
        name="Research Stage",
        description="Scan opportunities",
        department="research",
        parent_goal=goal_id,
        priority=Priority.HIGH,
    )
    t2 = TaskNode(
        task_id="t2",
        name="Build Stage",
        description="Assemble deliverable",
        department="engineering",
        parent_goal=goal_id,
        priority=Priority.HIGH,
        dependencies=["t1"],
    )
    graph.add_node(t1)
    graph.add_node(t2)
    return graph


async def _run_goal(executor: TaskExecutor, goal_id: str) -> Any:
    graph = _build_goal_graph(goal_id)

    async def runner(task: TaskNode, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "task_id": task.task_id,
            "status": "success",
            "summary": f"Executed '{task.name}' successfully.",
            "tools_used": task.tool_requirements or ["default_executor"],
        }

    return await executor.run(graph, handler=runner, timeout=30.0), graph


def _successful_executor(tmp_path) -> TaskExecutor:
    return TaskExecutor(
        router=TaskRouter(),
        scheduler=TaskScheduler(max_concurrency=2),
        verifier=TaskVerifier(),
        memory_writer=TaskMemoryWriter(backup_storage=str(tmp_path / "mem.json")),
        reflection_engine=TaskReflectionEngine(storage_path=str(tmp_path / "reflections.json")),
    )


class _MemorylessReflectionEngine:
    """Adversarial double: a reflection engine that pretends to reflect but
    never produces or persists any record (the Fourth Law'ed)."""

    def reflect_on_goal(self, graph: TaskGraph) -> None:
        return None

    def get_reflection(self, goal_id: str) -> None:
        return None


class TestFourthLawCompliance:
    """A goal that finishes cleanly must be COMPLETED with a persisted record."""

    async def test_completed_goal_requires_and_produces_reflection(self, tmp_path):
        executor = _successful_executor(tmp_path)
        report, graph = await _run_goal(executor, "goal_fourth_law_ok")

        assert report.status == TaskStatus.COMPLETED
        assert report.completed_tasks == report.total_tasks
        assert report.fourth_law_compliant is True

        # Post-goal reflection exists and is attached to the report
        assert report.reflection is not None
        record = executor.reflection_engine.get_reflection("goal_fourth_law_ok")
        assert record is not None
        assert record.goal_id == "goal_fourth_law_ok"

    async def test_reflection_record_is_persisted_to_memory(self, tmp_path):
        executor = _successful_executor(tmp_path)
        await _run_goal(executor, "goal_fourth_law_persist")

        storage_file = tmp_path / "reflections.json"
        assert storage_file.exists()  # NO MEMORY WITHOUT REFLECTION: it actually persisted

        persisted = json.loads(storage_file.read_text(encoding="utf-8"))
        assert "goal_fourth_law_persist" in persisted

    async def test_record_contains_fourth_law_sections(self, tmp_path):
        executor = _successful_executor(tmp_path)
        report, _graph = await _run_goal(executor, "goal_fourth_law_sections")

        record: ReflectionRecord = report.reflection
        # Fourth Law mandates: Lessons(improvements), Failures, Successes, Capability gaps
        for section in ("successes", "failures", "improvements", "opportunities"):
            assert hasattr(record, section)
            assert isinstance(getattr(record, section), list)
        # Successful completion always yields at least one evidence-backed success entry
        assert len(record.successes) >= 1


class TestFourthLawAdversarial:
    """The law must hold even under a lying reflection engine."""

    async def test_missing_reflection_blocks_completed_status(self, tmp_path):
        executor = TaskExecutor(
            router=TaskRouter(),
            scheduler=TaskScheduler(max_concurrency=2),
            verifier=TaskVerifier(),
            memory_writer=TaskMemoryWriter(backup_storage=str(tmp_path / "mem.json")),
            reflection_engine=_MemorylessReflectionEngine(),
        )
        report, _graph = await _run_goal(executor, "goal_fourth_law_attack")

        # All tasks succeeded and verified — yet the goal must NOT claim COMPLETED
        assert report.completed_tasks == report.total_tasks
        assert report.status is not TaskStatus.COMPLETED
        assert report.status == TaskStatus.INCOMPLETE
        assert report.fourth_law_compliant is False
        assert report.reflection is None

    async def test_incomplete_is_honest_but_never_false_failure(self, tmp_path):
        executor = TaskExecutor(
            router=TaskRouter(),
            scheduler=TaskScheduler(max_concurrency=2),
            verifier=TaskVerifier(),
            memory_writer=TaskMemoryWriter(backup_storage=str(tmp_path / "mem.json")),
            reflection_engine=_MemorylessReflectionEngine(),
        )
        report, _graph = await _run_goal(executor, "goal_fourth_law_honest")

        # No task actually failed: honest INCOMPLETE, not a fabricated FAILED
        assert report.failed_tasks == 0
        assert report.status == TaskStatus.INCOMPLETE
