"""Job Scan and Fit Scoring Engine (PWR-329).

Analyzes job listings, extracts required competencies, and calculates
global fit score, hard skill match, and keyword delta against user profile.
"""

from __future__ import annotations

import re
import hashlib
from typing import Any, Dict, List, Optional, Set
from jarvis.career.models import JobFitScore, UserCareerProfile
from jarvis.core.logger import get_logger

logger = get_logger("career.scanner")


class JobScanner:
    """Evaluates job descriptions against user career profile."""

    def __init__(self, profile: Optional[UserCareerProfile] = None):
        self.profile = profile or UserCareerProfile()

    @staticmethod
    def _extract_keywords(text: str) -> Set[str]:
        words = re.findall(r"\b[A-Za-z0-9+#.-]{2,}\b", text.lower())
        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "you", "will",
            "are", "have", "our", "work", "team", "role", "experience", "years"
        }
        return {w for w in words if w not in stop_words and len(w) > 2}

    def scan_job(
        self,
        job_title: str,
        company_name: str,
        description: str,
        job_url: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> JobFitScore:
        """Calculates ATS match and competency fit score for a job posting."""
        if not job_id:
            job_id = "job_" + hashlib.sha256(f"{company_name}_{job_title}".encode()).hexdigest()[:10]

        user_skills_lower = {s.lower() for s in self.profile.core_skills}
        user_domains_lower = {d.lower() for d in self.profile.domain_expertise}
        all_user_keywords = user_skills_lower | user_domains_lower

        desc_keywords = self._extract_keywords(description)

        # Match hard skills
        matched = []
        missing = []

        # Check explicit core skills
        for skill in self.profile.core_skills:
            if re.search(rf"\b{re.escape(skill.lower())}\b", description.lower()):
                matched.append(skill)
            else:
                missing.append(skill)

        matched_count = len(matched)
        if matched_count >= 5:
            hard_skills_score = min(100.0, 75.0 + (matched_count * 4.0))
        elif matched_count >= 2:
            hard_skills_score = 60.0 + (matched_count * 5.0)
        else:
            hard_skills_score = matched_count * 25.0

        # Keyword density match
        overlap = desc_keywords.intersection(all_user_keywords)
        soft_skills_score = min(100.0, 75.0 + (len(overlap) * 2.5))

        # Global score weighted: 65% hard skills, 35% domain/soft skills
        global_score = round((hard_skills_score * 0.65) + (soft_skills_score * 0.35), 1)

        # Recommendation threshold
        if global_score >= 75.0:
            recommendation = "Strong Fit - Prioritize Application"
        elif global_score >= 60.0:
            recommendation = "Moderate Fit - Tailor ATS Keywords"
        elif global_score >= 40.0:
            recommendation = "Stretch Role - Focus on Transferable Skills"
        else:
            recommendation = "Not Recommended - Low Competency Alignment"

        logger.info(
            f"Job scan complete: {job_title} at {company_name} -> Score: {global_score}% ({recommendation})"
        )

        return JobFitScore(
            job_id=job_id,
            job_title=job_title,
            company_name=company_name,
            job_url=job_url,
            global_score=global_score,
            hard_skills_score=round(hard_skills_score, 1),
            soft_skills_score=round(soft_skills_score, 1),
            matched_skills=matched,
            missing_skills=missing[:8],
            recommendation=recommendation
        )
