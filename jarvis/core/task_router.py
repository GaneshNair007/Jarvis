"""
JARVIS Task Router & Agent Assignment Layer (CEO & Department Model)
Enforces hierarchical management: Tasks do not pick agents.
The Central CEO Router evaluates task requirements, selects departments,
and delegates work to specialized worker agents through department managers.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskNode, Priority


class Assignment(BaseModel):
    task_id: str
    agent_id: str
    department: str
    assigned_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Department(BaseModel):
    id: str
    name: str
    manager_agent: str
    worker_agents: List[str]
    description: str = ""
    capabilities: List[str] = Field(default_factory=list)


class TaskRouter:
    """
    Central CEO Routing Engine.
    Maintains organizational structure across departments and resolves task-to-agent assignments.
    """

    def __init__(self):
        self.departments: Dict[str, Department] = {}
        self.agent_capabilities: Dict[str, List[str]] = {}
        self._initialize_default_departments()

    def _initialize_default_departments(self):
        # 1. Hackathon Department
        self.register_department(Department(
            id="hackathon",
            name="Hackathon & Innovation",
            manager_agent="hackathon_manager",
            worker_agents=[
                "hackathon_scout",
                "guideline_reader",
                "problem_selector",
                "prize_evaluator",
            ],
            description="Scouts, analyzes, and coordinates winning strategies for technical hackathons.",
            capabilities=["search_hackathons", "analyze_guidelines", "evaluate_prizes", "select_problem"],
        ))

        # 2. Engineering Department
        self.register_department(Department(
            id="engineering",
            name="Software Engineering & Systems",
            manager_agent="eng_manager",
            worker_agents=[
                "system_architect",
                "backend_developer",
                "frontend_developer",
                "test_engineer",
                "ast_code_mapper",
            ],
            description="Designs architecture, implements code, writes test suites, and refactors repos.",
            capabilities=["architecture_design", "create_repo", "build_mvp", "run_tests", "ast_analysis"],
        ))

        # 3. Research & Intelligence Department
        self.register_department(Department(
            id="research",
            name="Research & Intelligence",
            manager_agent="research_manager",
            worker_agents=[
                "web_scout",
                "citation_extractor",
                "competitive_analyst",
                "deep_reasoner",
            ],
            description="Deep web search, documentation synthesis, and technical feasibility studies.",
            capabilities=["web_search", "browse_page", "extract_citations", "deep_research"],
        ))

        # 4. Operations & Infrastructure Department
        self.register_department(Department(
            id="operations",
            name="Systems & Infrastructure Operations",
            manager_agent="ops_manager",
            worker_agents=[
                "sysadmin_worker",
                "network_probe",
                "sandbox_controller",
                "daemon_supervisor",
            ],
            description="Monitors host health, runs local subshells, and manages background daemons.",
            capabilities=["system_health", "execute_shell", "port_check", "process_monitor"],
        ))

        # 5. Security & Compliance Department
        self.register_department(Department(
            id="security",
            name="Cybersecurity & Secret Protection",
            manager_agent="security_manager",
            worker_agents=[
                "dlp_auditor",
                "permission_gate_agent",
                "entropy_secret_scanner",
                "merkle_integrity_auditor",
            ],
            description="Enforces 10-layer DLP shield, audits secret leakage, and checks privileges.",
            capabilities=["dlp_scan", "permission_broker", "entropy_scan", "merkle_audit"],
        ))

        # 6. Career & Opportunities Department
        self.register_department(Department(
            id="career",
            name="Career & Professional Growth",
            manager_agent="career_manager",
            worker_agents=[
                "internship_scout",
                "ats_resume_optimizer",
                "interview_evaluator",
                "gsoc_mentor_liaison",
            ],
            description="Tracks high-value internships, optimizes GitHub profiles, and prepares for GSoC.",
            capabilities=["internship_match", "ats_analysis", "profile_optimization", "gsoc_prep"],
        ))

    def register_department(self, dept: Department) -> None:
        self.departments[dept.id.lower()] = dept
        for worker in dept.worker_agents:
            if worker not in self.agent_capabilities:
                self.agent_capabilities[worker] = dept.capabilities

    def resolve_department(self, department_name: str) -> Optional[Department]:
        """Looks up department by ID or fuzzy name match."""
        key = department_name.lower().strip()
        if key in self.departments:
            return self.departments[key]
        for d in self.departments.values():
            if key in d.name.lower() or d.id in key:
                return d
        return None

    def assign_agent(self, task: TaskNode) -> Assignment:
        """
        CEO Agent Assignment Decision:
        1. Identifies the appropriate department.
        2. Inspects task requirements and tool needs.
        3. Selects the most specialized worker agent in that department.
        4. Binds the agent to the task.
        """
        dept = self.resolve_department(task.department)
        if not dept:
            # Fallback to engineering department
            dept = self.departments["engineering"]

        # If task explicitly declared an assigned_agent and it exists in dept, confirm it
        if task.assigned_agent and task.assigned_agent in dept.worker_agents:
            agent_id = task.assigned_agent
        else:
            # Match worker agent based on task keywords or tool requirements
            agent_id = self._select_worker_agent(dept, task)

        assignment = Assignment(
            task_id=task.task_id,
            agent_id=agent_id,
            department=dept.id,
            metadata={"manager": dept.manager_agent, "task_priority": task.priority.value},
        )
        task.assigned_agent = agent_id
        return assignment

    def _select_worker_agent(self, dept: Department, task: TaskNode) -> str:
        """Heuristic and capability matching of worker agents within a department."""
        task_text = f"{task.name} {task.description}".lower()

        # Department specific heuristics
        if dept.id == "hackathon":
            if "search" in task_text or "find" in task_text:
                return "hackathon_scout"
            if "rule" in task_text or "guide" in task_text:
                return "guideline_reader"
            if "prize" in task_text:
                return "prize_evaluator"
            return "problem_selector"

        if dept.id == "engineering":
            if "architect" in task_text or "design" in task_text:
                return "system_architect"
            if "test" in task_text or "verify" in task_text:
                return "test_engineer"
            if "repo" in task_text or "git" in task_text:
                return "backend_developer"
            return "backend_developer"

        if dept.id == "research":
            if "citation" in task_text or "verify" in task_text:
                return "citation_extractor"
            return "web_scout"

        if dept.id == "security":
            if "dlp" in task_text or "leak" in task_text:
                return "dlp_auditor"
            return "permission_gate_agent"

        # Default to first worker or manager
        return dept.worker_agents[0] if dept.worker_agents else dept.manager_agent


# Global Singleton Instance
task_router = TaskRouter()
