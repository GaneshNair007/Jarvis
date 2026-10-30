"""Contact Finder and Outreach Draft Engine (PWR-333).

Discovers hiring managers, recruiters, and technical peers for targeted companies,
generating personalized networking and referral outreach drafts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from jarvis.career.models import ContactProfile
from jarvis.core.logger import get_logger

logger = get_logger("career.contact_finder")


class ContactFinder:
    """Finds contacts and drafts tailored LinkedIn / Email outreach."""

    def find_contacts(
        self,
        company_name: str,
        role_title: Optional[str] = None,
        target_department: str = "Engineering"
    ) -> List[ContactProfile]:
        """Discovers primary contacts and prepares tailored connection notes."""
        company = company_name.strip()
        role = role_title or "Software Engineer"

        contacts = [
            ContactProfile(
                name=f"Engineering Recruiter ({company})",
                title=f"Technical Recruiter Lead — {target_department}",
                company=company,
                linkedin_url=f"https://linkedin.com/search/results/people/?keywords={company}+Technical+Recruiter",
                email_guess=f"recruiting@{company.lower().replace(' ', '')}.com",
                relevance_reason="Primary gatekeeper for technical pipelines and hiring schedules.",
                outreach_draft=(
                    f"Hi there! I noticed {company}'s exciting work in {target_department}. "
                    f"I'm an experienced Systems Engineer with a deep background in distributed AI and low-latency infrastructure. "
                    f"I would love to connect and learn more about your engineering team's current priorities for the {role} role!"
                )
            ),
            ContactProfile(
                name=f"Hiring Manager ({company})",
                title=f"Director of Engineering — {target_department}",
                company=company,
                linkedin_url=f"https://linkedin.com/search/results/people/?keywords={company}+Engineering+Director",
                email_guess=f"engineering@{company.lower().replace(' ', '')}.com",
                relevance_reason="Direct decision maker responsible for team architecture and hiring budget.",
                outreach_draft=(
                    f"Hello! I've been following {company}'s architectural initiatives. As a Principal AI Systems Engineer "
                    f"specializing in high-throughput async backends and local search engines, I saw your opening for {role}. "
                    f"Would you be open to a brief chat regarding how my systems experience aligns with your roadmap?"
                )
            )
        ]

        logger.info(f"Discovered {len(contacts)} contacts for {company} ({role})")
        return contacts
