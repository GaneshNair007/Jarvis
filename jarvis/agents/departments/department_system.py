"""
JARVIS Department System - Enforces company structure
"""
from __future__ import annotations
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class Department:
    id: str
    name: str
    manager: str
    workers: List[str]
    capabilities: List[str]

DEPARTMENTS = {
    "career": Department("career", "Career & Opportunities", "career_manager", ["internship_scout", "job_scout", "form_filler", "resume_optimizer"], ["job_search", "form_fill", "apply"]),
    "hackathon": Department("hackathon", "Hackathons & Innovation", "hackathon_manager", ["hackathon_scout", "guideline_analyzer", "problem_mediator", "repo_creator"], ["scout", "analyze", "build"]),
    "research": Department("research", "Research & Intelligence", "research_manager", ["web_scout", "paper_scout", "trend_scout"], ["research", "extract"]),
    "engineering": Department("engineering", "Software Engineering", "eng_manager", ["architect", "backend_dev", "frontend_dev", "tester"], ["code", "build", "test"]),
    "learning": Department("learning", "Learning & Growth", "learning_manager", ["assignment_agent", "tutor"], ["moodle", "assignments"]),
    "security": Department("security", "Security & Compliance", "security_manager", ["dlp_auditor", "permission_gate"], ["audit", "protect"]),
    "operations": Department("operations", "Operations & Infrastructure", "ops_manager", ["scheduler", "monitor"], ["deploy", "monitor"]),
}

class DepartmentManager:
    def __init__(self):
        self.departments = DEPARTMENTS

    def get_department(self, dept_id: str):
        return self.departments.get(dept_id)

    def get_all(self):
        return self.departments


dept_manager = DepartmentManager()
