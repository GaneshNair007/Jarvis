"""
Integration Tests for Goal Execution API Endpoint (/goals/execute)
Verifies:
  1. Hackathon 8-Stage DAG Execution via FastAPI Endpoint
  2. Engineering 5-Stage DAG Execution with AST and PR proposals
  3. Research 4-Stage DAG Execution with citations and synthesis
"""

import pytest
from fastapi.testclient import TestClient
from jarvis.api.server import app
from jarvis.db.session import init_db


@pytest.fixture(autouse=True)
def setup_database_schema():
    init_db()


@pytest.fixture(autouse=True)
def setup_test_db():
    from jarvis.db.session import init_db

    init_db()


@pytest.fixture
def client():
    return TestClient(app)


class TestGoalExecutionAPI:
    """Tests the /goals/execute endpoint end-to-end through FastAPI TestClient."""

    def test_execute_hackathon_goal_api(self, client):
        payload = {
            "title": "Help me find and win an AI hackathon in Pune",
            "description": "Scout hackathons, read rules, build architecture, generate repo",
            "pipeline_type": "hackathon",
            "priority": "HIGH",
        }
        response = client.post("/goals/execute", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["title"] == payload["title"]
        assert data["status"] == "completed"
        assert data["total_tasks"] == 8
        assert data["completed_tasks"] == 8
        assert data["failed_tasks"] == 0
        assert data["duration_seconds"] >= 0.0
        assert "t1" in data["task_results"]
        assert "t8" in data["task_results"]
        assert data["reflection"] is not None
        assert len(data["reflection"]["successes"]) >= 8

    def test_execute_engineering_goal_api(self, client):
        payload = {
            "title": "Refactor authentication subsystem and author Safe PR",
            "description": "AST audit, design, test, safe PR proposal",
            "pipeline_type": "engineering",
            "priority": "HIGH",
        }
        response = client.post("/goals/execute", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert data["total_tasks"] == 5
        assert data["completed_tasks"] == 5
        assert data["failed_tasks"] == 0
        assert "t1" in data["task_results"]

    def test_execute_research_goal_api(self, client):
        payload = {
            "title": "Deep research on multimodal agent systems",
            "description": "Scout, scrape, extract citations, synthesize",
            "pipeline_type": "research",
            "priority": "MEDIUM",
        }
        response = client.post("/goals/execute", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert data["total_tasks"] == 4
        assert data["completed_tasks"] == 4
        assert data["failed_tasks"] == 0
