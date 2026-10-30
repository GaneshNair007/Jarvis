"""Application Email Draft Engine (PWR-334).

Drafts professional email applications, referral inquiries, and interview
follow-ups with tailored value-propositions and attached asset notices.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from jarvis.career.models import UserCareerProfile
from jarvis.core.logger import get_logger

logger = get_logger("career.email_draft")


class ApplicationEmailDrafter:
    """Creates tailored email drafts for job submissions and follow-ups."""

    def draft_application_email(
        self,
        recipient_name: str,
        company_name: str,
        role_title: str,
        profile: Optional[UserCareerProfile] = None
    ) -> Dict[str, str]:
        """Formats a submission email tailored to the specific role and company."""
        p = profile or UserCareerProfile()

        subject = f"Application: {role_title} — {p.name}"
        body = f"""Hi {recipient_name},

I hope this note finds you well.

I am reaching out to formally submit my application for the {role_title} opening at {company_name}. With over 8 years of engineering experience architecting distributed AI platforms, millisecond local search indices, and autonomous tool-use agents, I believe my technical background is uniquely positioned to deliver immediate impact for {company_name}.

A quick overview of what I bring to the team:
• Architected private, low-latency AI backends combining SQLite FTS5 lexical matching and Qdrant vector retrieval.
• Scaled async distributed microservices processing >50k events/sec with rigorous zero-trust safety gates.
• Passionate about clean codebases, automated CI/CD validation, and deterministic AI reliability.

I have attached my tailored resume and would welcome the opportunity to discuss how my skill set matches your engineering goals.

Thank you for your time and consideration.

Best regards,

{p.name}
{p.title}
{p.email} | {p.location}
GitHub: https://github.com/GaneshNair007
"""
        logger.info(f"Drafted application email for {role_title} at {company_name}")
        return {
            "subject": subject,
            "body": body,
            "recipient_name": recipient_name,
            "company_name": company_name,
            "role_title": role_title
        }

