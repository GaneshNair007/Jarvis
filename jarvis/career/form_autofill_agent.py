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
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.logger import get_logger

logger = get_logger("career.form_autofill")


class CandidateProfile(BaseModel):
    first_name: str = "Ganesh"
    last_name: str = "Nair"
    full_name: str = "Ganesh Nair"
    email: str = ""
    phone: str = ""
    location: str = "Pune, Maharashtra, India"
    university: str = "Symbiosis Institute of Technology (SIT), Pune"
    degree: str = "B.Tech in Artificial Intelligence and Machine Learning"
    graduation_year: str = "2029"
    linkedin_url: str = "https://www.linkedin.com/in/ganesh-nair-8ab1a5378/"
    github_url: str = "https://github.com/GaneshNair007"
    portfolio_url: str = "https://github.com/GaneshNair007/Jarvis"
    core_skills: List[str] = Field(
        default_factory=lambda: [
            "Python", "C", "SQL", "Pandas", "NumPy", "Scikit-learn",
            "Data Preprocessing", "Supervised Learning", "Git", "GitHub",
            "Jupyter Notebook", "Excel", "Power BI",
        ]
    )
    hardware: str = ""


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
            "showcase_project": "Project JARVIS (105-Agent Autonomous Operating System)"
            if "agent" in combined_text or "ai" in combined_text
            else "AURA / AgriKavach",
            "candidate_name": self.profile.full_name,
        }

    def generate_essay_answer(self, prompt: str, word_limit: int = 150) -> str:
        """Return conservative draft text grounded in the candidate's resume."""
        p_lower = prompt.lower()
        if "why" in p_lower or "join" in p_lower or "interested" in p_lower:
            answer = (
                "I am a second-year B.Tech Artificial Intelligence and Machine Learning student at "
                "Symbiosis Institute of Technology, Pune. I am interested in applying my current "
                "foundations in Python, data analysis and machine learning while learning from an "
                "industry team. My resume includes team projects such as Signal Atlas, Nayan, "
                "CORTEX Cloud Autopilot, CarbonTerra and AI-Assisted Onion Quality Grading."
            )
        elif any(term in p_lower for term in ["project", "achievement", "proud", "challenging"]):
            answer = (
                "My resume describes several team-based academic and hackathon projects, including "
                "Signal Atlas (web-scraping and intelligence dashboard), Nayan (traffic-management "
                "prototype), CORTEX Cloud Autopilot (cloud-incident prototype), CarbonTerra "
                "(digital-sustainability prototype) and AI-Assisted Onion Quality Grading. "
                "I would add the exact individual contribution for the project most relevant to this role."
            )
        elif any(term in p_lower for term in ["strength", "skills", "background"]):
            answer = (
                "I am pursuing a B.Tech in Artificial Intelligence and Machine Learning at "
                "Symbiosis Institute of Technology, Pune. My resume lists Python, C, SQL, Pandas, "
                "NumPy, Scikit-learn, data preprocessing, supervised learning, Git, Excel and "
                "Power BI. I am continuing to strengthen these foundations through coursework and projects."
            )
        else:
            answer = (
                "I am a second-year B.Tech Artificial Intelligence and Machine Learning student "
                "at Symbiosis Institute of Technology, Pune, expected to graduate in 2029. "
                "My current skills and project experience are listed in my attached resume."
            )
        return " ".join(answer.split()[:max(1, word_limit)])

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
            elif (
                "phone" in label_clean
                or "mobile" in label_clean
                or "contact" in label_clean
                or "whatsapp" in label_clean
            ):
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
            elif f.field_type == "textarea" or any(
                w in label_clean for w in ["why", "tell us", "describe", "experience", "about yourself", "project"]
            ):
                essay = self.generate_essay_answer(f.label)
                filled_fields[fid] = essay
                essay_answers[f.label] = essay

            else:
                unmapped_fields.append(f.label)

        # Check readiness
        # Autofill is preparation only. A human must review every answer and submit.
        ready = False

        return FormAutofillResult(
            form_title=form_title,
            fit_score=round(
                len([skill for skill in self.profile.core_skills if skill.lower() in
                     (form_title + " " + " ".join(f.label for f in fields)).lower()])
                / max(1, len(self.profile.core_skills)), 2
            ),
            total_fields=len(fields),
            filled_fields=filled_fields,
            unmapped_fields=unmapped_fields,
            essay_answers=essay_answers,
            ready_for_submission=ready,
        )

    def autofill_web_form(
        self,
        url: str,
        headless: bool = True,
        dry_run: bool = False,
        allow_submit: bool = False,
        allow_private: bool = False,
        screenshot_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Drives an ephemeral Playwright browser session to locate DOM form fields,
        maps Ganesh Nair's profile to inputs/textareas, types verified values,
        and always pauses before submission. Submission is deliberately disabled here.
        """
        from jarvis.browser.context_manager import BrowserContextManager

        ctx_mgr = BrowserContextManager(headless=headless)
        filled_records: List[Dict[str, str]] = []
        submit_button_found = False
        screenshot_path = ""

        with ctx_mgr.research_context(allow_private=allow_private) as (context, page):
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")

            # Collect all inputs and textareas
            inputs = page.locator("input, textarea").all()
            for el in inputs:
                try:
                    el_type = (el.get_attribute("type") or "text").lower()
                    el_name = (el.get_attribute("name") or "").lower()
                    el_id = (el.get_attribute("id") or "").lower()
                    el_ph = (el.get_attribute("placeholder") or "").lower()
                    el_label = (el.get_attribute("aria-label") or "").lower()

                    descriptor = f"{el_name} {el_id} {el_ph} {el_label}"

                    val_to_fill = None

                    if el_type in ("text", "email", "tel", "url") or el.evaluate(
                        "node => node.tagName.toLowerCase() == 'textarea'"
                    ):
                        if "email" in descriptor or el_type == "email":
                            val_to_fill = self.profile.email
                        elif (
                            "phone" in descriptor
                            or "mobile" in descriptor
                            or "contact" in descriptor
                            or el_type == "tel"
                        ):
                            val_to_fill = self.profile.phone
                        elif "github" in descriptor:
                            val_to_fill = self.profile.github_url
                        elif "linkedin" in descriptor:
                            val_to_fill = self.profile.linkedin_url
                        elif "portfolio" in descriptor or "website" in descriptor:
                            val_to_fill = self.profile.portfolio_url
                        elif "first" in descriptor:
                            val_to_fill = self.profile.first_name
                        elif "last" in descriptor:
                            val_to_fill = self.profile.last_name
                        elif "name" in descriptor:
                            val_to_fill = self.profile.full_name
                        elif "university" in descriptor or "college" in descriptor:
                            val_to_fill = self.profile.university
                        elif "degree" in descriptor or "major" in descriptor:
                            val_to_fill = self.profile.degree
                        elif "location" in descriptor or "city" in descriptor:
                            val_to_fill = self.profile.location
                        elif el.evaluate("node => node.tagName.toLowerCase() == 'textarea'") or any(
                            q in descriptor for q in ["why", "project", "experience", "about", "essay"]
                        ):
                            val_to_fill = self.generate_essay_answer(descriptor)

                    if val_to_fill and not dry_run:
                        el.fill(val_to_fill)
                        filled_records.append(
                            {
                                "element": descriptor.strip(),
                                "type": el_type,
                                "value": val_to_fill[:50] + ("..." if len(val_to_fill) > 50 else ""),
                            }
                        )
                    elif val_to_fill and dry_run:
                        filled_records.append(
                            {
                                "element": descriptor.strip(),
                                "type": el_type,
                                "value": "[DRY RUN PREVIEW] " + val_to_fill[:50],
                            }
                        )
                except Exception as e:
                    logger.debug(f"Field fill skipped: {e}")

            # Check for submit buttons
            submit_candidates = page.locator(
                "button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Apply')"
            )
            submit_button_found = submit_candidates.count() > 0

            # Capture evidence screenshot
            if screenshot_dir:
                s_dir = Path(screenshot_dir)
                s_dir.mkdir(parents=True, exist_ok=True)
                s_file = s_dir / f"form_autofill_{int(time.time())}.png"
                page.screenshot(path=str(s_file))
                screenshot_path = str(s_file)

            # Fail-closed: this legacy helper can fill and preview only. It cannot submit.
            # The internship queue requires a separate review/approval flow.
            submitted = False

        return {
            "target_url": url,
            "candidate": self.profile.full_name,
            "total_fields_filled": len(filled_records),
            "fields_filled": filled_records,
            "submit_button_found": submit_button_found,
            "submitted": submitted,
            "human_approval_required": not submitted,
            "screenshot_evidence": screenshot_path,
            "status": "submitted" if submitted else "ready_for_human_review",
        }


# Global singleton instance
autonomous_form_filler = AutonomousFormFiller()
