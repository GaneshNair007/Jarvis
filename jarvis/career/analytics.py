"""Application Pipeline Tracker & Funnel Analytics (PWR-335).

Tracks submitted applications, conversion funnel ratios, response times,
and rejection pattern analytics with local JSON/SQLite storage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.career.models import ApplicationEntry
from jarvis.core.logger import get_logger

logger = get_logger("career.analytics")


class CareerPipelineAnalytics:
    """Manages the job application pipeline and calculates funnel conversion metrics."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or "data/career_pipeline.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.applications: Dict[str, ApplicationEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            for item in raw:
                entry = ApplicationEntry(**item)
                self.applications[entry.application_id] = entry
        except Exception as e:
            logger.warning(f"Failed to load career pipeline: {e}")

    def _save(self) -> None:
        try:
            data = [app.model_dump() for app in self.applications.values()]
            self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save career pipeline: {e}")

    def record_application(
        self,
        company_name: str,
        job_title: str,
        job_url: Optional[str] = None,
        fit_score: float = 0.0,
        status: str = "applied"
    ) -> ApplicationEntry:
        """Records a new application in the local pipeline ledger."""
        app_id = f"app_{company_name.lower().replace(' ', '_')}_{job_title.lower().replace(' ', '_')}"
        clean_id = "".join(c for c in app_id if c.isalnum() or c in ("_", "-"))

        entry = ApplicationEntry(
            application_id=clean_id,
            company_name=company_name,
            job_title=job_title,
            job_url=job_url,
            fit_score=fit_score,
            status=status
        )
        self.applications[clean_id] = entry
        self._save()
        logger.info(f"Recorded application {clean_id}: {job_title} at {company_name}")
        return entry

    def update_status(self, application_id: str, new_status: str, note: Optional[str] = None) -> Optional[ApplicationEntry]:
        """Updates the status of an existing application."""
        if application_id not in self.applications:
            return None
        app = self.applications[application_id]
        app.status = new_status
        if note:
            app.notes.append(note)
        self._save()
        logger.info(f"Updated application {application_id} to {new_status}")
        return app

    def list_applications(self, status: Optional[str] = None) -> List[ApplicationEntry]:
        """Returns applications filtered optionally by status."""
        apps = list(self.applications.values())
        if status:
            return [a for a in apps if a.status.lower() == status.lower()]
        return apps

    def analyze_patterns(self) -> Dict[str, Any]:
        """Computes funnel statistics, conversion metrics, and rejection trends."""
        total = len(self.applications)
        if total == 0:
            return {
                "total_applications": 0,
                "funnel": {"applied": 0, "screening": 0, "interview": 0, "offer": 0, "rejected": 0},
                "conversion_rates": {"screening_rate": 0.0, "interview_rate": 0.0, "offer_rate": 0.0},
                "average_fit_score": 0.0,
                "insights": ["No applications recorded yet. Use /job-scan or /record-application to begin."]
            }

        counts = {
            "saved": 0,
            "applied": 0,
            "screening": 0,
            "interview": 0,
            "offer": 0,
            "rejected": 0,
            "withdrawn": 0
        }

        total_score = 0.0
        for app in self.applications.values():
            s = app.status.lower()
            if s in counts:
                counts[s] += 1
            total_score += app.fit_score

        avg_score = round(total_score / total, 1)

        # Conversions
        active_applied = max(1, counts["applied"] + counts["screening"] + counts["interview"] + counts["offer"] + counts["rejected"])
        screening_rate = round((counts["screening"] + counts["interview"] + counts["offer"]) / active_applied * 100, 1)
        interview_rate = round((counts["interview"] + counts["offer"]) / active_applied * 100, 1)
        offer_rate = round(counts["offer"] / active_applied * 100, 1)

        insights = [
            f"Pipeline contains {total} tracked applications with an average fit score of {avg_score}%.",
            f"Screening conversion rate is {screening_rate}% across active applications."
        ]

        if counts["rejected"] > 0:
            insights.append(f"Rejected applications ({counts['rejected']}) indicate checking keyword match density on ATS resumes.")

        return {
            "total_applications": total,
            "funnel": counts,
            "conversion_rates": {
                "screening_rate": screening_rate,
                "interview_rate": interview_rate,
                "offer_rate": offer_rate
            },
            "average_fit_score": avg_score,
            "insights": insights
        }

