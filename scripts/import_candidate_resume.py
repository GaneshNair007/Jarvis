"""Import verified candidate facts from a local resume PDF into an ignored JSON file.

Usage:
  python scripts/import_candidate_resume.py "C:\\path\\to\\Ganesh_Nair_Resume.pdf"
Review the generated data/candidate_profile.json before using the application queue.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader


def extract_profile(pdf_path: Path) -> dict:
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
    if not text.strip():
        raise ValueError("No selectable text found in resume; use a text-based PDF.")

    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    phone_match = re.search(r"(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}", text)
    grad_match = re.search(r"20\d{2}\s*[-–]\s*(20\d{2})\s*\(Expected\)", text, re.I)
    degree_match = re.search(r"(B\.Tech[^\n]+)", text, re.I)
    if not all((email_match, phone_match, grad_match, degree_match)):
        raise ValueError("Could not confidently extract email, phone, expected graduation year and degree. "
                         "No profile was written; inspect the PDF text and correct the importer.")

    skills_section = re.search(
        r"TECHNICAL SKILLS\s*(.*?)(?:\n\s*CERTIFICATIONS|\Z)", text, re.I | re.S
    )
    skills = []
    if skills_section:
        for line in skills_section.group(1).splitlines():
            line = re.sub(r"\s+", " ", line).strip(" •-\t")
            if ":" in line:
                skills.extend(x.strip() for x in re.split(r",", line.split(":", 1)[1]) if x.strip())
    if not skills:
        raise ValueError("Could not extract the Technical Skills section; profile not written.")

    project_section = re.search(
        r"SELECTED PROJECTS\s*(.*?)(?:\n\s*ACHIEVEMENTS|\Z)", text, re.I | re.S
    )
    projects = []
    if project_section:
        for line in project_section.group(1).splitlines():
            clean = re.sub(r"\s+", " ", line).strip()
            if clean and not clean.lower().startswith(("worked on", "created a", "github", "project website", "demo video")):
                if len(clean) <= 100 and not clean.endswith("."):
                    projects.append(clean)
    achievements_section = re.search(
        r"ACHIEVEMENTS\s*(.*?)(?:\n\s*TECHNICAL SKILLS|\Z)", text, re.I | re.S
    )
    achievements = []
    if achievements_section:
        achievements = [
            re.sub(r"^[•*\-\s]+", "", re.sub(r"\s+", " ", line)).strip()
            for line in achievements_section.group(1).splitlines()
            if re.sub(r"^[•*\-\s]+", "", line).strip()
        ]

    return {
        "full_name": "Ganesh Nair",
        "email": email_match.group(0),
        "phone": phone_match.group(0),
        "location": "Pune, Maharashtra, India",
        "education": "B.Tech Artificial Intelligence & Machine Learning, Symbiosis Institute of Technology, Pune",
        "graduation_year": grad_match.group(1),
        "skills": list(dict.fromkeys(skills)),
        "projects": list(dict.fromkeys(projects)),
        "achievements": achievements,
        "target_roles": ["AI/ML Intern", "Python Developer Intern", "Generative AI Intern",
                         "Data Analyst Intern", "Software Engineering Intern"],
        "resume_path": str(pdf_path.resolve()),
        "profile_source": pdf_path.name,
        "profile_review_required": True,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: python scripts/import_candidate_resume.py "C:\\path\\to\\resume.pdf"')
        return 2
    source = Path(sys.argv[1]).expanduser()
    profile = extract_profile(source)
    destination = Path("data/candidate_profile.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Created {destination.resolve()}")
    print("REVIEW REQUIRED: verify every extracted field before using JARVIS.")
    print(json.dumps(profile, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
