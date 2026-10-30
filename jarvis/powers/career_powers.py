"""JARVIS Career-Ops Powers (PWR-328 to PWR-337).

Operational implementations for local job scanning, ATS resume generation,
cover-letter crafting, company research, contact discovery, email outreach,
pipeline analytics, interview preparation, and compensation negotiation.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any, Dict, List, Optional
from jarvis.career.service import career_service
from jarvis.core.logger import get_logger

logger = get_logger("powers.career")


def _safe_run_async(coro):
    """Safely executes an async coroutine from either sync or active async contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()
    return asyncio.run(coro)


class CareerPowers:
    """Implementations for Career-Ops domain capabilities."""

    def __init__(self):
        self.service = career_service

    def get_service_status(self) -> Dict[str, Any]:
        """PWR-328: Checks career service layer health, concurrency limit, and user profile."""
        profile = self.service.profile
        apps = self.service.list_applications()
        return {
            "power_id": "PWR-328",
            "status": "healthy",
            "candidate_name": profile.name,
            "target_roles": profile.target_roles,
            "tracked_applications_count": len(apps),
            "max_concurrency": 3,
        }

    def scan_job_listing(
        self,
        job_title: str,
        company_name: str,
        description: str,
        job_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """PWR-329: Job scan and fit scoring (scan.mjs equivalent)."""
        score = _safe_run_async(
            self.service.scan_job(
                job_title=job_title,
                company_name=company_name,
                description=description,
                job_url=job_url
            )
        )
        return {
            "power_id": "PWR-329",
            "job_id": score.job_id,
            "company_name": score.company_name,
            "job_title": score.job_title,
            "global_score": score.global_score,
            "hard_skills_score": score.hard_skills_score,
            "soft_skills_score": score.soft_skills_score,
            "matched_skills": score.matched_skills,
            "missing_skills": score.missing_skills,
            "recommendation": score.recommendation,
        }

    def generate_tailored_resume(
        self,
        job_title: str,
        company_name: str,
        target_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """PWR-330: Tailored ATS resume generation (generate-pdf.mjs equivalent)."""
        resume = _safe_run_async(
            self.service.generate_resume(
                job_title=job_title,
                company_name=company_name,
                target_keywords=target_keywords
            )
        )
        return {
            "power_id": "PWR-330",
            "resume_id": resume.resume_id,
            "file_path": resume.file_path,
            "ats_score": resume.ats_score,
            "included_keywords": resume.included_keywords,
        }

    def generate_cover_letter(
        self,
        job_title: str,
        company_name: str,
        key_challenges: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """PWR-331: Tailored cover-letter generation (cover mode equivalent)."""
        cover = _safe_run_async(
            self.service.generate_cover_letter(
                job_title=job_title,
                company_name=company_name,
                key_challenges=key_challenges
            )
        )
        return {
            "power_id": "PWR-331",
            "letter_id": cover.letter_id,
            "company_name": cover.company_name,
            "content": cover.content,
            "star_points": cover.star_points,
        }

    def research_company_brief(
        self,
        company_name: str,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """PWR-332: Company research brief (deep mode equivalent)."""
        dossier = _safe_run_async(
            self.service.research_company(
                company_name=company_name,
                domain=domain
            )
        )
        return {
            "power_id": "PWR-332",
            "company_name": dossier.company_name,
            "summary": dossier.summary,
            "culture_signals": dossier.culture_signals,
            "tech_stack": dossier.tech_stack,
            "recent_news": dossier.recent_news,
            "leadership": dossier.leadership,
            "glassdoor_rating": dossier.glassdoor_rating,
        }

    def find_company_contacts(
        self,
        company_name: str,
        role_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """PWR-333: Contact finder and outreach draft (contacto equivalent)."""
        contacts = _safe_run_async(
            self.service.find_contacts(
                company_name=company_name,
                role_title=role_title
            )
        )
        return {
            "power_id": "PWR-333",
            "company_name": company_name,
            "contacts_found": len(contacts),
            "contacts": [c.model_dump() for c in contacts],
        }

    def draft_application_email(
        self,
        recipient_name: str,
        company_name: str,
        role_title: str
    ) -> Dict[str, Any]:
        """PWR-334: Application email draft (email mode equivalent)."""
        draft = _safe_run_async(
            self.service.draft_email(
                recipient_name=recipient_name,
                company_name=company_name,
                role_title=role_title
            )
        )
        return {
            "power_id": "PWR-334",
            "subject": draft["subject"],
            "body": draft["body"],
            "recipient_name": draft["recipient_name"],
            "company_name": draft["company_name"],
            "role_title": draft["role_title"],
        }

    def analyze_application_pipeline(self) -> Dict[str, Any]:
        """PWR-335: Application pipeline analytics (analyze-patterns equivalent)."""
        stats = self.service.analyze_pipeline()
        return {
            "power_id": "PWR-335",
            **stats
        }

    def interview_prep_and_red_flags(
        self,
        role_title: str,
        company_name: str,
        job_description: Optional[str] = None,
        focus_tech: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """PWR-336: Interview prep, STAR scenarios, and red-flag checking."""
        prep = self.service.prepare_interview(
            role_title=role_title,
            company_name=company_name,
            focus_tech=focus_tech
        )
        red_flags = []
        if job_description:
            red_flags = self.service.check_red_flags(company_name, job_description)

        return {
            "power_id": "PWR-336",
            "role_title": prep.role_title,
            "company_name": prep.company_name,
            "star_questions": prep.star_questions,
            "technical_focus_areas": prep.technical_focus_areas,
            "questions_to_ask_team": prep.questions_to_ask_team,
            "red_flag_warnings": red_flags or prep.red_flag_warnings,
        }

    def analyze_offer_and_salary_gap(
        self,
        company_name: str,
        role_title: str,
        base_salary: float,
        bonus: float = 0.0,
        equity_annual_val: float = 0.0
    ) -> Dict[str, Any]:
        """PWR-337: Offer compensation analysis and negotiation script."""
        analysis = self.service.analyze_offer(
            company_name=company_name,
            role_title=role_title,
            base_salary=base_salary,
            bonus=bonus,
            equity_annual_val=equity_annual_val
        )
        return {
            "power_id": "PWR-337",
            "offer_id": analysis.offer_id,
            "company_name": analysis.company_name,
            "role_title": analysis.role_title,
            "total_comp": analysis.total_comp,
            "target_comp": analysis.target_comp,
            "gap": analysis.gap,
            "gap_percentage": analysis.gap_percentage,
            "verdict": analysis.verdict,
            "negotiation_script": analysis.negotiation_script,
        }


career_powers = CareerPowers()
