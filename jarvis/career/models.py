"""Data models for Career-Ops subsystem (PWR-328 to PWR-337)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserCareerProfile(BaseModel):
    name: str = "Ganesh Nair"
    title: str = "Principal AI Systems Architect"
    email: str = "nairganesh134@gmail.com"
    location: str = "San Francisco, CA (or Remote)"
    target_roles: List[str] = Field(default_factory=list)
    target_salary_min: float = 200000.0
    target_salary_currency: str = "USD"
    core_skills: List[str] = Field(default_factory=list)
    domain_expertise: List[str] = Field(default_factory=list)
    experience_summary: str = ""


class JobFitScore(BaseModel):
    job_id: str
    job_title: str
    company_name: str
    job_url: Optional[str] = None
    global_score: float  # 0.0 - 100.0
    hard_skills_score: float
    soft_skills_score: float
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    recommendation: str  # Strong Fit, Moderate Fit, Stretch Role, Not Recommended
    timestamp: str = Field(default_factory=_utc_now_iso)


class ResumeArtifact(BaseModel):
    resume_id: str
    job_id: Optional[str] = None
    file_path: str
    ats_score: float
    included_keywords: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=_utc_now_iso)


class CoverLetterArtifact(BaseModel):
    letter_id: str
    job_id: Optional[str] = None
    company_name: str
    content: str
    star_points: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=_utc_now_iso)


class CompanyDossier(BaseModel):
    company_name: str
    domain: Optional[str] = None
    summary: str
    culture_signals: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    recent_news: List[str] = Field(default_factory=list)
    leadership: List[str] = Field(default_factory=list)
    glassdoor_rating: Optional[float] = None
    red_flags: List[str] = Field(default_factory=list)


class ContactProfile(BaseModel):
    name: str
    title: str
    company: str
    linkedin_url: Optional[str] = None
    email_guess: Optional[str] = None
    relevance_reason: str
    outreach_draft: str


class ApplicationEntry(BaseModel):
    application_id: str
    company_name: str
    job_title: str
    job_url: Optional[str] = None
    status: str = "applied"  # saved, applied, screening, interview, offer, rejected, withdrawn
    fit_score: float = 0.0
    resume_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
    applied_date: str = Field(default_factory=_utc_now_iso)
    notes: List[str] = Field(default_factory=list)
    salary_offered: Optional[float] = None


class InterviewPrepSession(BaseModel):
    role_title: str
    company_name: str
    star_questions: List[Dict[str, str]] = Field(default_factory=list)
    technical_focus_areas: List[str] = Field(default_factory=list)
    questions_to_ask_team: List[str] = Field(default_factory=list)
    red_flag_warnings: List[str] = Field(default_factory=list)


class OfferAnalysis(BaseModel):
    offer_id: str
    company_name: str
    role_title: str
    base_salary: float
    bonus: float = 0.0
    equity_annual_val: float = 0.0
    total_comp: float
    target_comp: float
    gap: float
    gap_percentage: float
    verdict: str  # Meets Target, Below Target, Above Target
    negotiation_script: str
