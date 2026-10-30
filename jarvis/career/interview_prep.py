"""Interview Preparation and Red-Flag Checker (PWR-336).

Generates STAR-method behavioral questions, architectural interview scenarios,
reverse-interview inquiries, and company culture red flag warnings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from jarvis.career.models import InterviewPrepSession
from jarvis.core.logger import get_logger

logger = get_logger("career.interview_prep")


class InterviewPrepEngine:
    """Prepares users for technical, system design, and behavioral interviews."""

    def prepare_interview(
        self,
        role_title: str,
        company_name: str,
        focus_tech: Optional[List[str]] = None
    ) -> InterviewPrepSession:
        """Constructs a comprehensive interview readiness session."""
        tech_list = focus_tech or ["Distributed Systems", "Concurrency", "FastAPI", "SQLite FTS5", "Vector Search"]

        star_questions = [
            {
                "category": "Architecture & Scaling",
                "question": f"Describe a time you designed a mission-critical system for {role_title} that handled high concurrency. How did you ensure sub-second response times?",
                "star_framework": "Situation: Legacy latency bottlenecks; Task: Re-architect retrieval layer; Action: Fused lexical FTS5 and vector indices with async caching; Result: Reduced p99 latency by 85%."
            },
            {
                "category": "Conflict & Technical Disagreement",
                "question": "Tell me about a time you disagreed with a peer or leadership regarding technology selection. How did you resolve it?",
                "star_framework": "Situation: Debate over cloud API dependency vs local-first SQLite/Qdrant; Task: Justify local-first privacy; Action: Ran empirical latency & cost benchmarks; Result: Secured consensus for local-first design."
            },
            {
                "category": "Failure & Resilience",
                "question": "Walk me through an incident where a production service failed unexpectedly. How did you diagnose, mitigate, and prevent recurrence?",
                "star_framework": "Situation: Async worker queue saturation under unexpected burst load; Task: Prevent cascade failure; Action: Instituted backpressure and circuit breakers; Result: Zero data loss, automated recovery."
            }
        ]

        questions_to_ask_team = [
            f"What is the team's typical development-to-deployment cycle for new capabilities at {company_name}?",
            "How does the engineering organization balance feature velocity against technical debt and architectural refactoring?",
            "What are the biggest scalability or data integrity challenges the engineering team expects to face in the next 12 months?"
        ]

        red_flag_warnings = [
            "Excessive churn in engineering leadership over the past 12-18 months.",
            "Lack of dedicated CI/CD regression testing or reliance on manual production deployments.",
            "Vague descriptions of role ownership or ambiguous on-call rotation schedules."
        ]

        logger.info(f"Generated interview prep session for {role_title} at {company_name}")

        return InterviewPrepSession(
            role_title=role_title,
            company_name=company_name,
            star_questions=star_questions,
            technical_focus_areas=tech_list,
            questions_to_ask_team=questions_to_ask_team,
            red_flag_warnings=red_flag_warnings
        )

    def check_red_flags(self, company_name: str, job_description: str) -> List[str]:
        """Scans a job posting or company review text for toxic workplace red flags."""
        red_flags_found = []
        lower_desc = job_description.lower()

        patterns = [
            ("wearing many hats", "Potential lack of role boundaries and chronic understaffing."),
            ("fast-paced environment", "Often signals high pressure and tight deadlines."),
            ("must thrive under extreme pressure", "High risk of burnout and poorly managed delivery timelines."),
            ("work hard play hard", "Often signals expected unpaid overtime and blurred work-life balance."),
            ("rockstar", "May indicate immature engineering hierarchy or subjective performance reviews."),
            ("ninja", "May indicate lack of structured job scope."),
            ("guru", "May indicate unstructured organizational expectations."),
            ("unlimited pto", "Verify actual average days taken; can sometimes discourage planned vacation time.")
        ]

        for phrase, meaning in patterns:
            if phrase in lower_desc:
                red_flags_found.append(f"Flagged '{phrase}': {meaning}")

        if not red_flags_found:
            red_flags_found.append("No overt language red flags detected in posting.")

        logger.info(f"Red flag check for {company_name} found {len(red_flags_found)} signals")
        return red_flags_found
