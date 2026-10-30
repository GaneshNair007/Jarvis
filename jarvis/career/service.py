"""Career-Ops Service Layer (PWR-328).

Coordinates all career operations, concurrency limits (worker pool),
profile persistence, file adapters, and execution queues.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from jarvis.career.models import (
    ApplicationEntry,
    CompanyDossier,
    ContactProfile,
    CoverLetterArtifact,
    InterviewPrepSession,
    JobFitScore,
    OfferAnalysis,
    ResumeArtifact,
    UserCareerProfile
)
from jarvis.career.scanner import JobScanner
from jarvis.career.resume_generator import ResumeGenerator
from jarvis.career.cover_letter import CoverLetterGenerator
from jarvis.career.company_research import CompanyResearcher
from jarvis.career.contact_finder import ContactFinder
from jarvis.career.email_draft import ApplicationEmailDrafter
from jarvis.career.analytics import CareerPipelineAnalytics
from jarvis.career.interview_prep import InterviewPrepEngine
from jarvis.career.offer_analyzer import OfferAnalyzer
from jarvis.core.logger import get_logger

logger = get_logger("career.service")


class CareerOpsService:
    """Master service layer for all Career-Ops capabilities (PWR-328)."""

    def __init__(
        self,
        profile_path: str = "data/profile.yml",
        cv_path: str = "data/cv.md",
        max_concurrent_workers: int = 3
    ):
        self.profile_path = Path(profile_path)
        self.cv_path = Path(cv_path)
        self.semaphore = asyncio.Semaphore(max_concurrent_workers)
        self.profile = self._load_profile()

        # Initialize sub-engines
        self.scanner = JobScanner(self.profile)
        self.resume_generator = ResumeGenerator(master_cv_path=str(self.cv_path))
        self.cover_generator = CoverLetterGenerator()
        self.company_researcher = CompanyResearcher()
        self.contact_finder = ContactFinder()
        self.email_drafter = ApplicationEmailDrafter()
        self.pipeline_analytics = CareerPipelineAnalytics()
        self.interview_prep_engine = InterviewPrepEngine()
        self.offer_analyzer = OfferAnalyzer()

    def _load_profile(self) -> UserCareerProfile:
        """Loads user profile from YAML or returns defaults."""
        if self.profile_path.exists():
            try:
                raw = yaml.safe_load(self.profile_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return UserCareerProfile(**raw)
            except Exception as e:
                logger.warning(f"Failed to load profile.yml: {e}")
        return UserCareerProfile()

    def reload_profile(self) -> UserCareerProfile:
        """Refreshes the profile in-memory."""
        self.profile = self._load_profile()
        self.scanner = JobScanner(self.profile)
        return self.profile

    async def scan_job(
        self,
        job_title: str,
        company_name: str,
        description: str,
        job_url: Optional[str] = None
    ) -> JobFitScore:
        """PWR-329: Scans a job and returns fit score within concurrency boundary."""
        async with self.semaphore:
            score = self.scanner.scan_job(
                job_title=job_title,
                company_name=company_name,
                description=description,
                job_url=job_url
            )
            # Automatically record into pipeline ledger
            self.pipeline_analytics.record_application(
                company_name=company_name,
                job_title=job_title,
                job_url=job_url,
                fit_score=score.global_score,
                status="saved"
            )
            return score

    async def generate_resume(
        self,
        job_title: str,
        company_name: str,
        target_keywords: Optional[List[str]] = None
    ) -> ResumeArtifact:
        """PWR-330: Tailors ATS resume markdown and PDF output."""
        async with self.semaphore:
            keywords = target_keywords or self.profile.core_skills
            return self.resume_generator.generate_tailored_resume(
                job_title=job_title,
                company_name=company_name,
                target_keywords=keywords,
                profile=self.profile
            )

    async def generate_cover_letter(
        self,
        job_title: str,
        company_name: str,
        key_challenges: Optional[List[str]] = None
    ) -> CoverLetterArtifact:
        """PWR-331: Tailors role-specific cover letter."""
        async with self.semaphore:
            return self.cover_generator.generate_cover_letter(
                job_title=job_title,
                company_name=company_name,
                key_challenges=key_challenges,
                profile=self.profile
            )

    async def research_company(
        self,
        company_name: str,
        domain: Optional[str] = None
    ) -> CompanyDossier:
        """PWR-332: Conducts deep company background research."""
        async with self.semaphore:
            return self.company_researcher.research_company(
                company_name=company_name,
                domain=domain
            )

    async def find_contacts(
        self,
        company_name: str,
        role_title: Optional[str] = None
    ) -> List[ContactProfile]:
        """PWR-333: Finds key decision-maker contacts and prepares outreach drafts."""
        async with self.semaphore:
            return self.contact_finder.find_contacts(
                company_name=company_name,
                role_title=role_title
            )

    async def draft_email(
        self,
        recipient_name: str,
        company_name: str,
        role_title: str
    ) -> Dict[str, str]:
        """PWR-334: Drafts formal application email."""
        return self.email_drafter.draft_application_email(
            recipient_name=recipient_name,
            company_name=company_name,
            role_title=role_title,
            profile=self.profile
        )

    def analyze_pipeline(self) -> Dict[str, Any]:
        """PWR-335: Computes application pipeline conversion stats."""
        return self.pipeline_analytics.analyze_patterns()

    def update_application_status(
        self,
        application_id: str,
        new_status: str,
        note: Optional[str] = None
    ) -> Optional[ApplicationEntry]:
        """Updates status of a tracked application."""
        return self.pipeline_analytics.update_status(application_id, new_status, note)

    def list_applications(self, status: Optional[str] = None) -> List[ApplicationEntry]:
        """Lists tracked applications."""
        return self.pipeline_analytics.list_applications(status)

    def prepare_interview(
        self,
        role_title: str,
        company_name: str,
        focus_tech: Optional[List[str]] = None
    ) -> InterviewPrepSession:
        """PWR-336: Produces interview questions and STAR prep."""
        return self.interview_prep_engine.prepare_interview(
            role_title=role_title,
            company_name=company_name,
            focus_tech=focus_tech
        )

    def check_red_flags(self, company_name: str, job_description: str) -> List[str]:
        """PWR-336: Detects toxic workplace red flags in job descriptions."""
        return self.interview_prep_engine.check_red_flags(company_name, job_description)

    def analyze_offer(
        self,
        company_name: str,
        role_title: str,
        base_salary: float,
        bonus: float = 0.0,
        equity_annual_val: float = 0.0
    ) -> OfferAnalysis:
        """PWR-337: Analyzes compensation offer and provides negotiation script."""
        return self.offer_analyzer.analyze_offer(
            company_name=company_name,
            role_title=role_title,
            base_salary=base_salary,
            bonus=bonus,
            equity_annual_val=equity_annual_val,
            profile=self.profile
        )


career_service = CareerOpsService()

