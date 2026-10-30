"""Tailored Cover Letter Generator (PWR-331).

Generates role-specific, high-impact cover letters utilizing the STAR method
and exact value-add positioning for the target company.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.career.models import CoverLetterArtifact, UserCareerProfile
from jarvis.core.logger import get_logger

logger = get_logger("career.cover_letter")


class CoverLetterGenerator:
    """Generates tailored cover letters with STAR achievements."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or "data/cover_letters")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_cover_letter(
        self,
        job_title: str,
        company_name: str,
        key_challenges: Optional[List[str]] = None,
        profile: Optional[UserCareerProfile] = None
    ) -> CoverLetterArtifact:
        """Drafts a STAR-aligned tailored cover letter."""
        p = profile or UserCareerProfile()
        letter_id = f"cover_{company_name.lower().replace(' ', '_')}_{job_title.lower().replace(' ', '_')}"
        clean_id = "".join(c for c in letter_id if c.isalnum() or c in ("_", "-"))

        challenges_text = ""
        if key_challenges:
            challenges_text = f"Specifically, addressing {', '.join(key_challenges[:3])} aligns directly with my engineering focus."

        star_points = [
            f"Architected high-throughput distributed systems scaling to >50k req/s with sub-15ms p99 latency.",
            f"Spearheaded autonomous AI agent pipelines integrating lexical FTS5 and vector indices for millisecond recall.",
            f"Instituted zero-trust safety gates and automated DLP redaction securing mission-critical workflows."
        ]

        star_bullets = "\n".join([f"- **Impact:** {pt}" for pt in star_points])

        content = f"""Dear Hiring Team at {company_name},

I am writing to express my strong interest in the {job_title} position at {company_name}. With over 8 years of engineering experience architecting distributed AI systems, high-concurrency infrastructure, and privacy-preserving multi-agent platforms, I am confident in delivering immediate value to your engineering organization.

{challenges_text}

Throughout my career, I have focused on solving demanding technical challenges:
{star_bullets}

{company_name}'s commitment to engineering excellence resonates deeply with my personal philosophy of building fast, resilient, and deterministic systems. I welcome the opportunity to discuss how my technical expertise can support your roadmap.

Thank you for your consideration.

Sincerely,
{p.name}
{p.email} | {p.location}
"""

        # Save letter
        file_path = self.output_dir / f"{clean_id}.md"
        file_path.write_text(content, encoding="utf-8")

        logger.info(f"Generated tailored cover letter for {job_title} at {company_name}")

        return CoverLetterArtifact(
            letter_id=clean_id,
            company_name=company_name,
            content=content,
            star_points=star_points
        )

