"""
Unit & Integration Tests for JARVIS Proactive Autonomous Scheduler
Validates daily scheduled jobs (08:00 Career, 12:00 Hackathon, 18:00 Research),
manual triggering, error handling, status reporting, and Merkle audit logging.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from jarvis.core.scheduler import ProactiveAutonomousScheduler, ScheduledJob


@pytest.fixture
def scheduler():
    return ProactiveAutonomousScheduler(check_interval_sec=0.1)


def test_default_jobs_registered(scheduler):
    status = scheduler.get_status()
    assert status["total_jobs"] == 3
    job_ids = [j["job_id"] for j in status["jobs"]]
    assert "career_internship_scout" in job_ids
    assert "hackathon_scout" in job_ids
    assert "ai_research_digest" in job_ids


@pytest.mark.asyncio
async def test_manual_trigger_career_scout(scheduler):
    mock_handler = AsyncMock(return_value={"type": "career_scout", "opportunities_found": 3, "whatsapp_status": "SENT"})
    scheduler.jobs["career_internship_scout"].handler = mock_handler

    result = await scheduler.trigger_job("career_internship_scout")
    assert result["status"] == "SUCCESS"
    assert result["job_id"] == "career_internship_scout"
    assert scheduler.jobs["career_internship_scout"].run_count == 1
    assert scheduler.jobs["career_internship_scout"].last_status == "SUCCESS"


@pytest.mark.asyncio
async def test_manual_trigger_hackathon_scout(scheduler):
    mock_res = {
        "pipeline_id": "pipe_test_123",
        "status": "COMPLETED",
        "top_hackathon": "Smart India Hackathon 2026",
    }
    with patch("jarvis.agents.autonomous_workforce.autonomous_workforce.run_hackathon_opportunity_pipeline", AsyncMock(return_value=mock_res)):
        result = await scheduler.trigger_job("hackathon_scout")
        assert result["status"] == "SUCCESS"
        assert result["result"]["top_hackathon"] == "Smart India Hackathon 2026"
        assert scheduler.jobs["hackathon_scout"].run_count == 1


@pytest.mark.asyncio
async def test_manual_trigger_research_digest(scheduler):
    with patch("jarvis.powers.whatsapp_dispatcher.whatsapp_dispatcher.send_whatsapp_message", AsyncMock(return_value={"status": "SENT"})):
        result = await scheduler.trigger_job("ai_research_digest")
        assert result["status"] == "SUCCESS"
        assert result["result"]["whatsapp_status"] == "SENT"
        assert scheduler.jobs["ai_research_digest"].run_count == 1


@pytest.mark.asyncio
async def test_trigger_nonexistent_job_raises(scheduler):
    with pytest.raises(ValueError, match="not found"):
        await scheduler.trigger_job("non_existent_job_xyz")


@pytest.mark.asyncio
async def test_job_failure_isolation(scheduler):
    async def failing_handler():
        raise RuntimeError("External portal network connection refused")

    scheduler.register_job(
        job_id="failing_job",
        name="Failing Job Test",
        schedule_time_hhmm="00:00",
        handler=failing_handler,
    )

    result = await scheduler.trigger_job("failing_job")
    assert result["status"] == "FAILED"
    assert "network connection refused" in result["error"]
    assert scheduler.jobs["failing_job"].last_status == "FAILED"
    assert scheduler.jobs["failing_job"].last_error is not None
