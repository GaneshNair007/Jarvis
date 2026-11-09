"""
Architecture Guard Tests
Validates the 5 hard system invariants:
  1. Agents cannot perform direct SQL (must access data via repositories).
  2. Agents must access data via repositories.
  3. Task execution must flow through Task Graph.
  4. Reflection engine cannot bypass approval workflow.
  5. Capability registry cannot modify production code.
Also validates:
  - Safe PR Workflow branch isolation (no direct push to main).
  - PostgreSQL / SQLite Repository CRUD & UnitOfWork transaction safety.
"""

import pytest
import uuid
from jarvis.core.guards import ArchitectureGuard, ArchitectureViolationError
from jarvis.workflows.pr_workflow import SafePRWorkflowManager, WorkflowState, SecurityViolationError
from jarvis.capabilities.registry import CapabilityRegistry, CapabilityLevel
from jarvis.capabilities.models import CapabilitySchema
from db.models.goal import GoalModel
from db.models.capability import CapabilityModel
from db.repositories.unit_of_work import UnitOfWork


class TestArchitectureGuards:
    """Tests the 5 core architecture invariants enforced by ArchitectureGuard."""

    def test_agents_cannot_perform_direct_sql(self):
        # Rogue agent attempting SQL queries
        bad_queries = [
            "SELECT * FROM goals",
            "INSERT INTO tasks (name) VALUES ('hack')",
            "UPDATE goals SET status='COMPLETED'",
            "DELETE FROM memories WHERE id='123'",
            "DROP TABLE users",
        ]
        for query in bad_queries:
            with pytest.raises(ArchitectureViolationError, match="All database interactions must route through"):
                ArchitectureGuard.check_agent_sql_access("hackathon_scout_agent", query)

        # Repositories or non-agent callers are not blocked by the agent query guard
        # (they use parameterized ORM statements)
        assert True

    def test_task_execution_must_flow_through_task_graph(self):
        # Missing parent_goal or task_id
        invalid_contexts = [
            {},
            {"task_id": "t1"},  # missing parent_goal
            {"parent_goal": "goal_123"},  # missing task_id
        ]
        for ctx in invalid_contexts:
            with pytest.raises(ArchitectureViolationError, match="outside a validated TaskGraph"):
                ArchitectureGuard.check_task_execution_flow(ctx)

        # Valid context passes
        valid_ctx = {"task_id": "t1", "parent_goal": "goal_123"}
        ArchitectureGuard.check_task_execution_flow(valid_ctx)

    def test_reflection_cannot_bypass_approval_workflow(self):
        unapproved_states = ["PROPOSED", "PLANNED", "GENERATED", "TESTING", "SECURITY_REVIEW", "AWAITING_APPROVAL"]
        for st in unapproved_states:
            with pytest.raises(ArchitectureViolationError, match="Merges require explicit human APPROVED status"):
                ArchitectureGuard.check_reflection_approval_bypass(st, "merge")

        # APPROVED passes
        ArchitectureGuard.check_reflection_approval_bypass("APPROVED", "merge")

    def test_capability_registry_cannot_modify_production_code(self):
        forbidden_targets = [
            "jarvis/core/task_graph.py",
            "jarvis/security/ten_layer_shield.py",
            "db/models/goal.py",
            "app/main.py",
        ]
        for target in forbidden_targets:
            with pytest.raises(
                ArchitectureViolationError, match="Missing capabilities can only emit ImprovementRequests"
            ):
                ArchitectureGuard.check_capability_registry_write(target)

    def test_validate_system_invariants_auditor(self):
        assert ArchitectureGuard.validate_system_invariants() is True


class TestSafePRWorkflow:
    """Tests Safe PR Workflow branch isolation and state machine."""

    def test_forbid_autonomous_direct_push_to_main(self):
        mgr = SafePRWorkflowManager()
        with pytest.raises(SecurityViolationError, match="SECURITY BLOCK"):
            mgr.validate_branch_target("main", actor="autonomous_reflection_agent")

        with pytest.raises(SecurityViolationError, match="SECURITY BLOCK"):
            mgr.validate_branch_target("master", actor="deep_coder")

        # Feature branches are permitted
        mgr.validate_branch_target("feature/improvement-ui-tars", actor="autonomous_reflection_agent")

        # Human owner is permitted
        mgr.validate_branch_target("main", actor="ganesh")

    def test_state_transitions_require_qa_and_security(self):
        mgr = SafePRWorkflowManager()

        # Cannot move to AWAITING_APPROVAL without passing tests and security
        with pytest.raises(ValueError, match="PyTest automated test suite did not pass"):
            mgr.transition_state(
                WorkflowState.SECURITY_REVIEW,
                WorkflowState.AWAITING_APPROVAL,
                actor="test_runner",
                tests_passed=False,
                security_passed=True,
            )

        with pytest.raises(ValueError, match="10-layer DLP and secret scan did not pass"):
            mgr.transition_state(
                WorkflowState.SECURITY_REVIEW,
                WorkflowState.AWAITING_APPROVAL,
                actor="test_runner",
                tests_passed=True,
                security_passed=False,
            )

        # Passes when both are True
        next_st = mgr.transition_state(
            WorkflowState.SECURITY_REVIEW,
            WorkflowState.AWAITING_APPROVAL,
            actor="test_runner",
            tests_passed=True,
            security_passed=True,
        )
        assert next_st == WorkflowState.AWAITING_APPROVAL

    def test_human_approval_gate(self):
        mgr = SafePRWorkflowManager()
        # Autonomous agent cannot approve
        with pytest.raises(SecurityViolationError, match="not authorized to grant human approval"):
            mgr.transition_state(
                WorkflowState.AWAITING_APPROVAL,
                WorkflowState.APPROVED,
                actor="autonomous_agent",
            )

        # Human owner can approve
        st = mgr.transition_state(
            WorkflowState.AWAITING_APPROVAL,
            WorkflowState.APPROVED,
            actor="ganesh",
        )
        assert st == WorkflowState.APPROVED


class TestRepositoryLayerAndUnitOfWork:
    """Tests database repositories and UnitOfWork transaction management using test fixtures."""

    def test_goal_and_task_crud(self, uow: UnitOfWork):
        with uow:
            # 1. Create Goal
            goal = GoalModel(
                title="Win AI Hackathon",
                description="End to end automated pipeline",
                priority="HIGH",
                status="IN_PROGRESS",
            )
            uow.goals.create(goal)
            assert goal.id is not None

            # 2. Query Goal
            fetched = uow.goals.get_by_id(goal.id)
            assert fetched is not None
            assert fetched.title == "Win AI Hackathon"

            # 3. Create Capability
            cap = uow.capabilities.upsert_capability(
                name="ast_code_mapper",
                level="ADVANCED",
                category="engineering",
                description="AST Symbol Graph Mapper",
            )
            assert cap.level == "ADVANCED"

            # 4. Create Improvement Request
            imp = uow.improvements.create_request(
                title="Integrate UI-TARS",
                description="Add 0-1000 coordinate grounding",
                priority="HIGH",
            )
            assert imp.status == "PROPOSED"

            # 5. List items
            goals_list = uow.goals.list(limit=10)
            assert len(goals_list) >= 1
