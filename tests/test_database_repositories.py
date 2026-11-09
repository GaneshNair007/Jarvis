"""
Comprehensive Tests for JARVIS Database, Repository Layer, Unit of Work, and Redis State
Tests:
  1. UnitOfWork ACID Transaction Commit & Rollback
  2. Goal & Task Repositories CRUD Operations
  3. DAG Dependencies & Special `get_unblocked_tasks()` Query
  4. Agent Workforce Dynamic Lifecycle State Transitions
  5. Execution Repository & Tool Call Telemetry
  6. Memory Repository & Semantic Content Search
  7. Reflection Repository & Retrospective Insights
  8. Opportunity Repository Score Ranking & Hackathon Filtering
  9. Scheduler Repository Due Task Retrieval
  10. Artifact Repository File Tracking & SHA-256 Checksums
  11. Knowledge Graph Repository (Nodes, Directed Edges, BFS Shortest Path)
  12. EventBus Domain Event Publishing and Subscriptions
  13. Redis Real-Time Agent State Store (with Local Fallback)
  14. End-to-End GoalService and TaskService Operational Flow
"""

import datetime
import os
import uuid
import pytest
from sqlalchemy.orm import Session, sessionmaker

from jarvis.db.session import create_test_engine, Base
from jarvis.db.unit_of_work import UnitOfWork
from jarvis.db.models import (
    GoalModel,
    TaskModel,
    TaskGraphModel,
    TaskDependencyModel,
    DepartmentModel,
    AgentModel,
    AssignmentModel,
    ExecutionModel,
    MemoryModel,
    ReflectionModel,
    OpportunityModel,
    ArtifactModel,
    ScheduleModel,
    AuditModel,
    KnowledgeNodeModel,
    KnowledgeEdgeModel,
    AgentLifecycleModel,
)
from jarvis.db.events import (
    event_bus,
    TaskCreatedEvent,
    TaskCompletedEvent,
    GoalCompletedEvent,
    OpportunityDiscoveredEvent,
    AgentLifecycleEvent,
)
from jarvis.db.redis_state import RedisAgentStateStore
from jarvis.core.task_graph import TaskGraph, TaskNode, Priority
from jarvis.services.goal_service import GoalService
from jarvis.services.task_service import TaskService
from jarvis.services.agent_service import AgentService
from jarvis.services.opportunity_service import OpportunityService


@pytest.fixture
def test_db_session():
    """Provides isolated SQLite in-memory engine and session for each test."""
    test_engine = create_test_engine("sqlite:///:memory:")
    TestingSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionFactory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def uow_factory(test_db_session):
    """Provides UnitOfWork bound to test session."""

    def _factory():
        return UnitOfWork(session=test_db_session)

    return _factory


class TestUnitOfWorkAndTransactions:
    """Tests ACID transaction atomicity, commit, and rollback."""

    def test_unit_of_work_commit_persists(self, uow_factory, test_db_session):
        with uow_factory() as uow:
            goal = uow.goals.create_goal(title="Autonomous JARVIS", description="Build AI OS")
            uow.commit()

        queried = test_db_session.query(GoalModel).filter_by(title="Autonomous JARVIS").first()
        assert queried is not None
        assert queried.description == "Build AI OS"
        assert queried.status == "PENDING"

    def test_unit_of_work_rollback_on_exception(self, uow_factory, test_db_session):
        with pytest.raises(RuntimeError):
            with uow_factory() as uow:
                uow.goals.create_goal(title="Failed Goal", description="Should rollback")
                uow.flush()
                raise RuntimeError("Simulated transaction crash")

        queried = test_db_session.query(GoalModel).filter_by(title="Failed Goal").first()
        assert queried is None


class TestGoalAndTaskRepositories:
    """Tests Goal and Task CRUD and DAG status transitions."""

    def test_task_crud_and_completion_timestamps(self, uow_factory):
        with uow_factory() as uow:
            goal = uow.goals.create_goal(title="Win Hackathon")
            graph = uow.tasks.create_task_graph(goal_id=goal.id, graph_name="Hackathon_DAG")
            uow.flush()

            task = uow.tasks.create_task(
                task_graph_id=graph.id,
                goal_id=goal.id,
                task_key="t1",
                name="Scout Problem Statements",
                description="Browse Devfolio",
                department="hackathon",
                priority="HIGH",
            )
            uow.commit()
            task_id = task.id

        # Update task status to COMPLETED
        with uow_factory() as uow:
            updated = uow.tasks.update_task_status(task_id, "COMPLETED", outputs={"statements": 5})
            uow.commit()
            assert updated.status == "COMPLETED"
            assert updated.outputs["statements"] == 5
            assert updated.completed_at is not None


class TestDAGDependenciesAndUnblockedQuery:
    """Tests the critical `get_unblocked_tasks()` query for DAG scheduling."""

    def test_dag_dependency_unblocking_progression(self, uow_factory):
        """
        DAG: t1 (root) -> t2 (child)
        When t1 is PENDING, t1 is READY and t2 is BLOCKED.
        When t1 is COMPLETED, t2 unblocks to READY.
        """
        with uow_factory() as uow:
            goal = uow.goals.create_goal(title="Pipeline Goal")
            graph = uow.tasks.create_task_graph(goal_id=goal.id)
            uow.flush()

            t1 = uow.tasks.create_task(
                task_graph_id=graph.id,
                goal_id=goal.id,
                task_key="t1",
                name="Root Task",
                description="",
                department="research",
            )
            t2 = uow.tasks.create_task(
                task_graph_id=graph.id,
                goal_id=goal.id,
                task_key="t2",
                name="Dependent Task",
                description="",
                department="engineering",
            )
            uow.flush()

            # t2 depends on t1
            uow.dependencies.add_dependency(task_id=t2.id, depends_on_task_id=t1.id)
            uow.commit()
            graph_id = graph.id
            t1_id = t1.id
            t2_id = t2.id

        # Phase 1: Evaluate unblocked tasks
        with uow_factory() as uow:
            unblocked_phase1 = uow.tasks.get_unblocked_tasks(graph_id)
            uow.commit()
            unblocked_keys = [t.task_key for t in unblocked_phase1]
            assert "t1" in unblocked_keys
            assert "t2" not in unblocked_keys

            # Check that t2 was transitioned to BLOCKED
            t2_ref = uow.tasks.get_task(t2_id)
            assert t2_ref.status == "BLOCKED"

        # Phase 2: Complete t1
        with uow_factory() as uow:
            uow.tasks.update_task_status(t1_id, "COMPLETED", outputs={"status": "ok"})
            uow.commit()

        # Phase 3: Re-evaluate unblocked tasks
        with uow_factory() as uow:
            unblocked_phase2 = uow.tasks.get_unblocked_tasks(graph_id)
            uow.commit()
            unblocked_keys2 = [t.task_key for t in unblocked_phase2]
            # t2 should now be unblocked and marked READY!
            assert "t2" in unblocked_keys2
            t2_ref = uow.tasks.get_task(t2_id)
            assert t2_ref.status == "READY"


class TestAgentWorkforceLifecycle:
    """Tests dynamic agent spawning, pausing, resuming, and retirement."""

    def test_agent_dynamic_lifecycle_transitions(self, uow_factory):
        with uow_factory() as uow:
            agent = uow.agents.register_agent(
                agent_key="hackathon_scout_01",
                name="Hackathon Scout Specialist",
                role="Web Scout",
                model_name="gemini-2.5-flash",
                capabilities=["web_search", "devfolio_scraper"],
            )
            uow.commit()
            agent_id = agent.id

        with uow_factory() as uow:
            history1 = uow.agents.get_lifecycle_history(agent_id)
            assert len(history1) == 1
            assert history1[0].state == "created"

            # Transition: PAUSED
            uow.agents.update_status(agent_id, "PAUSED", reason="Idle timeout")
            uow.commit()

        with uow_factory() as uow:
            # Transition: RESUMED
            uow.agents.update_status(agent_id, "ACTIVE", reason="New hackathon found")
            # Transition: RETIRED
            uow.agents.update_status(agent_id, "RETIRED", reason="Goal complete")
            uow.commit()

        with uow_factory() as uow:
            history = uow.agents.get_lifecycle_history(agent_id)
            states = [h.state for h in history]
            assert states == ["created", "paused", "active", "retired"]


class TestExecutionRepository:
    """Tests tool execution recording and duration auditing."""

    def test_record_tool_call_execution(self, uow_factory):
        with uow_factory() as uow:
            goal = uow.goals.create_goal(title="Tool Goal")
            graph = uow.tasks.create_task_graph(goal_id=goal.id)
            task = uow.tasks.create_task(
                task_graph_id=graph.id,
                goal_id=goal.id,
                task_key="t_tool",
                name="Run Obscura",
                description="",
                department="research",
            )
            uow.commit()
            task_id = task.id

        with uow_factory() as uow:
            exec_rec = uow.executions.record_execution(
                task_id=task_id,
                tool_name="obscura_browser",
                input_data={"url": "https://devpost.com"},
                output_data={"title": "Devpost AI Hackathons", "events_found": 12},
                status="SUCCESS",
                execution_time=1.42,
            )
            uow.commit()
            exec_id = exec_rec.id

        with uow_factory() as uow:
            queried = uow.executions.get_execution(exec_id)
            assert queried is not None
            assert queried.tool_name == "obscura_browser"
            assert queried.execution_time == 1.42
            assert queried.output_data["events_found"] == 12


class TestMemoryAndReflectionRepositories:
    """Tests permanent semantic memory and post-goal retrospective storage."""

    def test_memory_storage_and_search(self, uow_factory):
        with uow_factory() as uow:
            uow.memories.store_memory(
                category="hackathon",
                content={"event": "hackathon_found", "name": "Pune AI Summit", "prize": "10000 USD"},
                importance_score=0.9,
            )
            uow.memories.store_memory(
                category="engineering",
                content={"snippet": "FastAPI with Task Graph DAG", "perf": "sub-10ms"},
                importance_score=0.8,
            )
            uow.commit()

        with uow_factory() as uow:
            results = uow.memories.search_memory(term="Pune")
            assert len(results) == 1
            assert "Pune AI Summit" in str(results[0].content)

    def test_reflection_repository_retrospective(self, uow_factory):
        with uow_factory() as uow:
            goal = uow.goals.create_goal(title="Reflection Goal")
            uow.commit()
            goal_id = goal.id

        with uow_factory() as uow:
            refl = uow.reflections.add_reflection(
                goal_id=goal_id,
                successes=["Completed 8/8 tasks without human intervention"],
                failures=[],
                improvements=["Optimize Kokoro TTS buffer pre-allocation"],
                opportunities=["Submit project to GSoC 2026 organizations"],
                metrics={"completion_rate": 100.0, "total_seconds": 18.2},
            )
            uow.commit()
            refl_id = refl.id

        with uow_factory() as uow:
            refls = uow.reflections.get_goal_reflections(goal_id)
            assert len(refls) == 1
            assert "Completed 8/8 tasks" in refls[0].successes[0]
            assert "GSoC 2026" in refls[0].opportunities[0]


class TestOpportunityAndSchedulerRepositories:
    """Tests career opportunity discovery and autonomous recurring schedules."""

    def test_opportunity_score_ranking(self, uow_factory):
        with uow_factory() as uow:
            uow.opportunities.record_opportunity(
                opportunity_type="hackathon",
                title="Global Agent Hackathon",
                source="Devpost",
                score=0.95,
                justification="Agent track with $50k prize",
            )
            uow.opportunities.record_opportunity(
                opportunity_type="internship",
                title="Google DeepMind Research Intern",
                source="Google Careers",
                score=0.99,
                justification="Matches multi-agent coding experience",
            )
            uow.opportunities.record_opportunity(
                opportunity_type="hackathon",
                title="Local College Hackathon",
                source="Campus",
                score=0.55,
            )
            uow.commit()

        with uow_factory() as uow:
            top = uow.opportunities.get_top_opportunities(limit=2)
            assert len(top) == 2
            assert top[0].score == 0.99  # DeepMind intern
            assert top[1].score == 0.95  # Global Agent hackathon

            best_hacks = uow.opportunities.get_best_hackathons(min_score=0.75)
            assert len(best_hacks) == 1
            assert best_hacks[0].title == "Global Agent Hackathon"

    def test_scheduler_due_tasks_retrieval(self, uow_factory):
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5)

        with uow_factory() as uow:
            uow.schedules.add_schedule(
                task_name="Daily Career Scan",
                cron_expression="0 8 * * *",
                next_run=past_time,  # Due now
            )
            uow.schedules.add_schedule(
                task_name="Weekly Benchmark",
                cron_expression="0 0 * * 0",
                next_run=future_time,  # Not due
            )
            uow.commit()

        with uow_factory() as uow:
            due = uow.schedules.get_due_schedules()
            assert len(due) == 1
            assert due[0].task_name == "Daily Career Scan"


class TestKnowledgeGraphRepository:
    """Tests knowledge graph nodes, weighted directed edges, and BFS pathfinding."""

    def test_knowledge_graph_traversal_and_shortest_path(self, uow_factory):
        """
        Graph:
        Ganesh (person) ────KNOWS────► Python (language) ────POWERS────► FastAPI (framework)
        """
        with uow_factory() as uow:
            n_ganesh = uow.knowledge.create_node(node_type="person", name="Ganesh")
            n_python = uow.knowledge.create_node(node_type="language", name="Python")
            n_fastapi = uow.knowledge.create_node(node_type="framework", name="FastAPI")
            uow.flush()

            uow.knowledge.create_edge(
                source_node_id=n_ganesh.id, target_node_id=n_python.id, relationship="KNOWS", strength=1.0
            )
            uow.knowledge.create_edge(
                source_node_id=n_python.id, target_node_id=n_fastapi.id, relationship="POWERS", strength=0.9
            )
            uow.commit()

            ganesh_id = n_ganesh.id
            python_id = n_python.id
            fastapi_id = n_fastapi.id

        with uow_factory() as uow:
            related = uow.knowledge.find_related(ganesh_id)
            assert len(related) == 1
            assert related[0].name == "Python"

            # BFS Shortest Path: Ganesh -> Python -> FastAPI
            path = uow.knowledge.find_path(start_node_id=ganesh_id, end_node_id=fastapi_id)
            assert path == [ganesh_id, python_id, fastapi_id]


class TestEventBusAndRedisState:
    """Tests reactive event publishing and real-time Redis agent status tracking."""

    def test_event_bus_pub_sub(self):
        event_bus.clear()
        received_events = []

        def on_opportunity(event: OpportunityDiscoveredEvent):
            received_events.append(event)

        event_bus.subscribe("opportunity_discovered", on_opportunity)

        sample_event = OpportunityDiscoveredEvent(
            opportunity_id="opp_123",
            opportunity_type="hackathon",
            title="MIT AI Hackathon",
            score=0.98,
            source="MIT",
        )
        event_bus.publish(sample_event)

        assert len(received_events) == 1
        assert received_events[0].title == "MIT AI Hackathon"
        assert received_events[0].score == 0.98

    def test_redis_agent_state_store_live_tracking(self):
        store = RedisAgentStateStore()
        store.clear()

        # Update status
        store.set_agent_status(
            department="hackathon",
            agent_name="hackathon_scout",
            status="RUNNING",
            current_task="Analyzing Devpost rules",
            progress=65,
        )

        status = store.get_agent_status("hackathon", "hackathon_scout")
        assert status is not None
        assert status["status"] == "RUNNING"
        assert status["current_task"] == "Analyzing Devpost rules"
        assert status["progress"] == 65

        # Query all active agents
        fleet = store.list_active_agents()
        assert len(fleet) >= 1
        assert any(a["agent_name"] == "hackathon_scout" for a in fleet)


class TestServicesEndToEnd:
    """Tests end-to-end integration across GoalService and TaskService."""

    def test_goal_service_and_task_service_flow(self, uow_factory):
        goal_service = GoalService(uow_factory=uow_factory)
        task_service = TaskService(uow_factory=uow_factory)

        # 1. Create Goal
        goal = goal_service.create_goal(title="Full Brain Test", description="Testing all layers")

        # 2. Decompose into TaskGraph
        graph = TaskGraph(goal_id=str(goal.id))
        t1 = TaskNode(task_id="t1", name="Step 1", description="Init", department="research", parent_goal=str(goal.id))
        t2 = TaskNode(
            task_id="t2",
            name="Step 2",
            description="Code",
            department="engineering",
            parent_goal=str(goal.id),
            dependencies=["t1"],
        )
        graph.add_node(t1)
        graph.add_node(t2)

        graph_id = goal_service.store_task_graph_dag(goal.id, graph)

        # 3. Unblocked Tasks -> t1
        unblocked = task_service.get_ready_unblocked_tasks(graph_id)
        assert len(unblocked) == 1
        assert unblocked[0].task_key == "t1"

        # 4. Start & Complete t1
        task_service.start_task(unblocked[0].id, agent_name="web_scout", department="research")
        task_service.complete_task(unblocked[0].id, outputs={"research": "done"})

        # 5. Now t2 becomes unblocked!
        unblocked2 = task_service.get_ready_unblocked_tasks(graph_id)
        assert len(unblocked2) == 1
        assert unblocked2[0].task_key == "t2"

        # 6. Complete t2 and complete Goal
        task_service.start_task(unblocked2[0].id, agent_name="backend_developer", department="engineering")
        task_service.complete_task(unblocked2[0].id, outputs={"code": "deployed"})

        completed_goal = goal_service.complete_goal(goal.id)
        assert completed_goal.status == "COMPLETED"
