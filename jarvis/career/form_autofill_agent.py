"""
JARVIS Autonomous Application Form Autofill & Opportunity Radar Agent
Empowers JARVIS to evaluate job, internship, and hackathon applications against
Ganesh Nair's professional profile, score alignment, and autonomously generate
field-by-field autofill payloads (or drive browser form submissions).

Operator Profile:
- Name: Ganesh Nair
- Email: nairganesh134@gmail.com
- Phone: +91 9324094474
- Location: Pune, India
- University: Symbiosis Institute of Technology (SIT), Pune (B.Tech AI & ML)
- LinkedIn: https://www.linkedin.com/in/ganesh-nair-8ab1a5378/
- GitHub: https://github.com/GaneshNair007
- Target Track: GSoC 2026/2027 | AI Systems Engineer | Distributed Agent Architect
"""

from __future__ import annotations

import re
import json
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.logger import get_logger

logger = get_logger("career.form_autofill")


class CandidateProfile(BaseModel):
    first_name: str = "Ganesh"
    last_name: str = "Nair"
    full_name: str = "Ganesh Nair"
    email: str = "nairganesh134@gmail.com"
    phone: str = "+919324094474"
    location: str = "Pune, Maharashtra, India"
    university: str = "Symbiosis Institute of Technology (SIT), Pune"
    degree: str = "B.Tech in Artificial Intelligence and Machine Learning"
    graduation_year: str = "2027"
    linkedin_url: str = "https://www.linkedin.com/in/ganesh-nair-8ab1a5378/"
    github_url: str = "https://github.com/GaneshNair007"
    portfolio_url: str = "https://github.com/GaneshNair007/Jarvis"
    core_skills: List[str] = Field(default_factory=lambda: [
        "Autonomous Multi-Agent Systems",
        "Python (Asyncio, FastAPI)",
        "Model Context Protocol (FastMCP)",
        "PyTorch & Computer Vision (OpenCV)",
        "AES-256-GCM Hardware Vaults",
        "Abstract Syntax Tree (AST) Code Mapping",
        "Distributed Task Graph Scheduling",
        "NVIDIA RTX 4050 Edge ML Inference",
    ])
    hardware: str = "NVIDIA GeForce RTX 4050 (6GB VRAM) Laptop GPU"


class FormField(BaseModel):
    field_id: str
    label: str
    field_type: str = "text"  # text, email, tel, url, textarea, select, checkbox
    required: bool = True
    options: Optional[List[str]] = None


class FormAutofillResult(BaseModel):
    form_title: str
    fit_score: float
    total_fields: int
    filled_fields: Dict[str, Any]
    unmapped_fields: List[str]
    essay_answers: Dict[str, str]
    ready_for_submission: bool


class AutonomousFormFiller:
    """
    Intelligent agent that maps arbitrary job, internship, and hackathon
    application forms to Ganesh Nair's profile and synthesizes technical essay responses.
    """

    def __init__(self, profile: Optional[CandidateProfile] = None):
        self.profile = profile or CandidateProfile()

    def evaluate_opportunity_fit(
        self,
        title: str,
        description: str,
        requirements: List[str],
    ) -> Dict[str, Any]:
        """
        Calculates alignment score between Ganesh's skills and opportunity requirements.
        Highlights matching strengths and recommended project showcases.
        """
        matched_skills = []
        missing_skills = []

        combined_text = f"{title} {description} {' '.join(requirements)}".lower()

        for skill in self.profile.core_skills:
            # Check for keyword matches
            keywords = skill.lower().replace("(", "").replace(")", "").split()
            if any(kw in combined_text for kw in keywords if len(kw) > 3):
                matched_skills.append(skill)

        # High-leverage domain matches
        if any(term in combined_text for term in ["python", "agent", "llm", "ai", "machine learning", "vision"]):
            score = round(min(0.70 + (len(matched_skills) * 0.05), 0.99), 2)
        else:
            score = 0.65

        recommendation = "HIGHLY RECOMMENDED" if score >= 0.85 else ("RECOMMENDED" if score >= 0.70 else "OPTIONAL")

        return {
            "title": title,
            "fit_score": score,
            "recommendation": recommendation,
            "matched_skills": matched_skills,
            "showcase_project": "Project JARVIS (105-Agent Autonomous Operating System)" if "agent" in combined_text or "ai" in combined_text else "AURA / AgriKavach",
            "candidate_name": self.profile.full_name,
        }

    def generate_essay_answer(self, prompt: str, word_limit: int = 150) -> str:
        """
        Synthesizes technical, grounded essay answers to standard application questions.
        """
        p_lower = prompt.lower()

        if "why" in p_lower and ("interested" in p_lower or "join" in p_lower or "apply" in p_lower):
            return (
                f"I am deeply passionate about engineering autonomous systems and applied AI. "
                f"At SIT Pune, I have architected Project JARVIS—an autonomous operating system running 105 concurrent "
                f"micro-agents and an AES-256-GCM zero-leak security shield. This role aligns perfectly with my focus on "
                f"low-latency backend concurrency, Model Context Protocol integration, and building reliable developer tooling."
            )

        if "project" in p_lower or "achievement" in p_lower or "proud" in p_lower or "challenging" in p_lower:
            return (
                f"My most challenging project is Project JARVIS (github.com/GaneshNair007/Jarvis). "
                f"I engineered an asymmetric hybrid compute topology distributing low-latency Kokoro-TTS and Faster-Whisper "
                f"onto my laptop's NVIDIA RTX 4050 GPU while routing cloud reasoning models through a fail-closed DLP firewall. "
                f"I implemented an Aider-style AST codebase knowledge graph and verified the entire system with 80+ passing test cases."
            )

        if "strength" in p_lower or "skills" in p_lower or "background" in p_lower:
            return (
                f"My core strengths are systems-level Python (Asyncio/FastAPI), autonomous agent design, and verifiable security. "
                f"I build software with test-driven rigor, cryptographic auditability (Merkle chains), and strict git hygiene. "
                f"I am currently preparing for GSoC 2026/2027 with open-source contributions in runtime ergonomics and compiler AST analysis."
            )

        # Generic default technical response
        return (
            f"As an AI Systems Engineer pursuing B.Tech AI & ML at SIT Pune, I specialize in autonomous multi-agent systems, "
            f"Model Context Protocol architectures, and edge GPU acceleration on NVIDIA RTX hardware. "
            f"You can review my open-source code and contributions at github.com/GaneshNair007."
        )

    def autofill_form(
        self,
        form_title: str,
        fields: List[FormField],
    ) -> FormAutofillResult:
        """
        Autonomously fills an application form given its field schema.
        Maps personal credentials and generates tailored essay answers.
        """
        filled_fields: Dict[str, Any] = {}
        unmapped_fields: List[str] = []
        essay_answers: Dict[str, str] = {}

        for f in fields:
            label_clean = f.label.lower()
            fid = f.field_id

            # Name mappings
            if "first" in label_clean and "name" in label_clean:
                filled_fields[fid] = self.profile.first_name
            elif "last" in label_clean and "name" in label_clean:
                filled_fields[fid] = self.profile.last_name
            elif "name" in label_clean or "full name" in label_clean:
                filled_fields[fid] = self.profile.full_name

            # Contact
            elif "email" in label_clean:
                filled_fields[fid] = self.profile.email
            elif "phone" in label_clean or "mobile" in label_clean or "contact" in label_clean or "whatsapp" in label_clean:
                filled_fields[fid] = self.profile.phone
            elif "city" in label_clean or "location" in label_clean or "address" in label_clean:
                filled_fields[fid] = self.profile.location

            # Links
            elif "linkedin" in label_clean:
                filled_fields[fid] = self.profile.linkedin_url
            elif "github" in label_clean:
                filled_fields[fid] = self.profile.github_url
            elif "portfolio" in label_clean or "website" in label_clean or "project url" in label_clean:
                filled_fields[fid] = self.profile.portfolio_url

            # Education
            elif "university" in label_clean or "college" in label_clean or "institution" in label_clean:
                filled_fields[fid] = self.profile.university
            elif "degree" in label_clean or "major" in label_clean or "branch" in label_clean:
                filled_fields[fid] = self.profile.degree
            elif "graduat" in label_clean or "year" in label_clean or "batch" in label_clean:
                filled_fields[fid] = self.profile.graduation_year

            # Subjective essay questions
            elif f.field_type == "textarea" or any(w in label_clean for w in ["why", "tell us", "describe", "experience", "about yourself", "project"]):
                essay = self.generate_essay_answer(f.label)
                filled_fields[fid] = essay
                essay_answers[f.label] = essay

            else:
                unmapped_fields.append(f.label)

        # Check readiness
        ready = len(unmapped_fields) == 0 or all(not f.required for f in fields if f.label in unmapped_fields)

        return FormAutofillResult(
            form_title=form_title,
            fit_score=0.96,
            total_fields=len(fields),
            filled_fields=filled_fields,
            unmapped_fields=unmapped_fields,
            essay_answers=essay_answers,
            ready_for_submission=ready,
        )


# Global singleton instance
autonomous_form_filler = AutonomousFormFiller()
