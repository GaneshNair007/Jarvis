"""
JARVIS Proactive Autonomous Background Scheduler
Runs persistent, scheduled background loops for:
  - 08:00 IST: Career & High-Stipend Internship Scout (Unstop, LinkedIn, Wellfound)
  - 12:00 IST: Hackathon Scout & Winner Pipeline (Devfolio, Unstop Pune & pan-India)
  - 18:00 IST: AI Research & GitHub Trending Digest (arXiv, Papers, GitHub)

Zero external daemon dependencies: powered by native asyncio timing loops with
fault-tolerant error isolation, task telemetry, and immediate manual trigger support.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional

from jarvis.core.logger import get_logger
from jarvis.security.ten_layer_shield import jarvis_security_suite

logger = get_logger("core.scheduler")


@dataclass
class ScheduledJob:
    job_id: str
    name: str
    schedule_time_hhmm: str  # Format "HH:MM" in 24-hr local time
    handler: Callable[[], Coroutine[Any, Any, Dict[str, Any]]]
    enabled: bool = True
    last_run_timestamp: Optional[float] = None
    last_status: str = "PENDING"
    run_count: int = 0
    last_result: Dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None


class ProactiveAutonomousScheduler:
    """
    Central background scheduler orchestrating daily proactive intelligence loops for Ganesh.
    """

    def __init__(self, check_interval_sec: float = 30.0):
        self.check_interval_sec = check_interval_sec
        self.jobs: Dict[str, ScheduledJob] = {}
        self._loop_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._register_default_jobs()

    def _register_default_jobs(self) -> None:
        """Registers the 3 core scheduled routines for Ganesh."""
        # 1. 08:00 Career & Internship Scout
        self.register_job(
            job_id="career_internship_scout",
            name="Morning Career & High-Stipend Internship Scout",
            schedule_time_hhmm="08:00",
            handler=self._job_career_scout,
        )

        # 2. 12:00 Hackathon Opportunity & Scaffold Pipeline
        self.register_job(
            job_id="hackathon_scout",
            name="Midday Hackathon Recon & Autonomous Scaffolder",
            schedule_time_hhmm="12:00",
            handler=self._job_hackathon_scout,
        )

        # 3. 18:00 AI Research & GitHub Trending Digest
        self.register_job(
            job_id="ai_research_digest",
            name="Evening AI Research & GitHub Trending Digest",
            schedule_time_hhmm="18:00",
            handler=self._job_research_digest,
        )

    def register_job(
        self,
        job_id: str,
        name: str,
        schedule_time_hhmm: str,
        handler: Callable[[], Coroutine[Any, Any, Dict[str, Any]]],
        enabled: bool = True,
    ) -> None:
        """Adds a scheduled job to the registry."""
        self.jobs[job_id] = ScheduledJob(
            job_id=job_id,
            name=name,
            schedule_time_hhmm=schedule_time_hhmm,
            handler=handler,
            enabled=enabled,
        )
        logger.info(f"Scheduler registered: [{job_id}] '{name}' at {schedule_time_hhmm} daily.")

    async def _job_career_scout(self) -> Dict[str, Any]:
        """08:00 Routine: discovers internship leads; no automatic external message."""
        from jarvis.core.web_recon import web_opportunity_recon

        logger.info("Executing 08:00 Career & Internship Scout routine...")
        opportunities = await web_opportunity_recon.search_live_hackathons(
            query="AI software engineer internship graduate research internship",
            location="India",
            limit=5,
        )
        return {
            "type": "career_scout",
            "status": "discovery_only" if opportunities else "unavailable",
            "opportunities_found": len(opportunities),
            "opportunities": opportunities,
            "notification": {
                "status": "not_requested",
                "message": "No email or WhatsApp notification was sent by the scheduled discovery job.",
            },
        }

    async def _job_hackathon_scout(self) -> Dict[str, Any]:
        """12:00 Routine: Mobilizes 105-agent workforce for Devfolio/Unstop hackathons."""
        from jarvis.agents.autonomous_workforce import autonomous_workforce

        logger.info("Executing 12:00 Midday Hackathon Workforce Swarm...")
        result = await autonomous_workforce.run_hackathon_opportunity_pipeline(
            target_phone="+919324094474",
            location="India",
            candidate_name="Ganesh",
        )
        return result

    async def _job_research_digest(self) -> Dict[str, Any]:
        """18:00 Routine: discovers current AI research and open-source project pages."""
        from jarvis.powers.browser_powers import browser_powers

        logger.info("Executing 18:00 live AI Research & GitHub discovery routine...")
        queries = (
            "latest AI agent open source projects GitHub",
            "recent research papers multi agent systems LLM 2026",
            "local LLM inference tools open source release",
        )
        discoveries: List[Dict[str, Any]] = []
        provider_errors: List[str] = []
        for query in queries:
            try:
                result = browser_powers.search_web(query, max_results=5)
                if result.get("status") != "completed":
                    provider_errors.append(str(result.get("message") or "Live search unavailable"))
                    continue
                for item in result.get("results", []):
                    discoveries.append(
                        {
                            **item,
                            "query": query,
                            "verification_status": "discovery_only",
                        }
                    )
            except Exception as exc:
                provider_errors.append(str(exc)[:240])

        # These are discovery links only. No scheduled external notification is sent.
        return {
            "type": "ai_research_digest",
            "status": "discovery_only" if discoveries else "unavailable",
            "discoveries_count": len(discoveries),
            "discoveries": discoveries,
            "provider_errors": provider_errors,
            "notification": {
                "status": "not_requested",
                "message": "No email or WhatsApp notification was sent by the scheduled discovery job.",
            },
        }

    async def trigger_job(self, job_id: str) -> Dict[str, Any]:
        """Immediately executes a scheduled job on demand."""
        if job_id not in self.jobs:
            raise ValueError(f"Job '{job_id}' not found in scheduler registry.")

        job = self.jobs[job_id]
        logger.info(f"Manual trigger initiated for job '{job.name}' ({job_id}).")
        job.last_status = "RUNNING"
        start_ts = time.time()

        try:
            result = await job.handler()
            raw_status = str(result.get("status", "") if isinstance(result, dict) else "").strip().lower()
            status_map = {
                "success": "SUCCESS",
                "completed": "SUCCESS",
                "discovery_only": "PARTIAL",
                "completed_local_only": "PARTIAL",
                "partial": "PARTIAL",
                "partial_failure": "PARTIAL_FAILURE",
                "unavailable": "UNAVAILABLE",
                "failed": "FAILED",
                "security_halt": "FAILED",
                "cancelled": "FAILED",
            }
            job_status = status_map.get(raw_status, "UNVERIFIED")
            job.last_status = job_status
            job.last_run_timestamp = time.time()
            job.run_count += 1
            job.last_result = result if isinstance(result, dict) else {"result": result}
            job.last_error = (
                "Handler returned no verifiable execution status."
                if job_status == "UNVERIFIED"
                else (
                    str(result.get("error") or result.get("message") or job_status)
                    if job_status in {"PARTIAL_FAILURE", "UNAVAILABLE", "FAILED"}
                    else None
                )
            )

            audit_event = (
                "SCHEDULED_JOB_SUCCESS"
                if job_status == "SUCCESS"
                else "SCHEDULED_JOB_UNVERIFIED"
                if job_status == "UNVERIFIED"
                else "SCHEDULED_JOB_NON_SUCCESS"
            )
            jarvis_security_suite.layer9_audit.log_event(
                audit_event,
                f"Job '{job_id}' status={job_status} after {round(time.time() - start_ts, 2)}s",
            )
            return {
                "status": job_status,
                "job_id": job_id,
                "duration_sec": round(time.time() - start_ts, 3),
                "result": result,
                **({"error": job.last_error} if job.last_error else {}),
            }
        except Exception as exc:
            job.last_status = "FAILED"
            job.last_error = str(exc)
            logger.error(f"Scheduled job '{job_id}' encountered error: {exc}", exc_info=True)
            jarvis_security_suite.layer9_audit.log_event(
                "SCHEDULED_JOB_FAILED",
                f"Job '{job_id}' failed: {exc}",
            )
            return {"status": "FAILED", "job_id": job_id, "error": str(exc)}

    def get_status(self) -> Dict[str, Any]:
        """Returns census and status of all configured scheduled jobs."""
        now_str = datetime.datetime.now().strftime("%H:%M")
        job_reports = []
        for job in self.jobs.values():
            job_reports.append(
                {
                    "job_id": job.job_id,
                    "name": job.name,
                    "schedule_time": job.schedule_time_hhmm,
                    "enabled": job.enabled,
                    "last_run": datetime.datetime.fromtimestamp(job.last_run_timestamp).isoformat()
                    if job.last_run_timestamp
                    else None,
                    "last_status": job.last_status,
                    "run_count": job.run_count,
                    "last_error": job.last_error,
                }
            )
        return {
            "current_time_hhmm": now_str,
            "total_jobs": len(self.jobs),
            "is_running": self._is_running,
            "jobs": job_reports,
        }

    async def _run_loop(self) -> None:
        """Internal background polling loop checking current time against schedule."""
        self._is_running = True
        logger.info("JARVIS Proactive Autonomous Scheduler background daemon started.")
        while self._is_running:
            try:
                now = datetime.datetime.now()
                current_hhmm = now.strftime("%H:%M")
                current_epoch_day = now.date().toordinal()

                for job_id, job in self.jobs.items():
                    if not job.enabled:
                        continue
                    if job.schedule_time_hhmm == current_hhmm:
                        # Check if already executed today
                        if job.last_run_timestamp:
                            last_date = datetime.datetime.fromtimestamp(job.last_run_timestamp).date().toordinal()
                            if last_date == current_epoch_day:
                                continue  # Already executed today
                        # Trigger execution asynchronously
                        asyncio.create_task(self.trigger_job(job_id))

            except Exception as e:
                logger.error(f"Error in scheduler tick: {e}")

            await asyncio.sleep(self.check_interval_sec)

    def start(self) -> None:
        """Starts background loop if not already running."""
        if not self._is_running:
            self._is_running = True
            try:
                loop = asyncio.get_running_loop()
                self._loop_task = loop.create_task(self._run_loop())
            except RuntimeError:
                pass  # Loop will be started with server lifespan

    def stop(self) -> None:
        """Stops background loop gracefully."""
        self._is_running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()


# Global Singleton Instance
proactive_scheduler = ProactiveAutonomousScheduler()
