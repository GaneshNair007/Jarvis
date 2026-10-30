"""Career-Ops REST API Routes (PWR-328 to PWR-337).

Exposes endpoints for job scanning, ATS resume generation, cover letter creation,
company research, contact discovery, application tracking, interview prep, and offer negotiation.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jarvis.powers.career_powers import career_powers

router = APIRouter(prefix="/api/v1/career", tags=["career-ops"])


class JobScanRequest(BaseModel):
    job_title: str
    company_name: str
    description: str
    job_url: Optional[str] = None


class ResumeRequest(BaseModel):
    job_title: str
    company_name: str
    target_keywords: Optional[List[str]] = None


class CoverLetterRequest(BaseModel):
    job_title: str
    company_name: str
    key_challenges: Optional[List[str]] = None


class CompanyResearchRequest(BaseModel):
    company_name: str
    domain: Optional[str] = None


class ContactFinderRequest(BaseModel):
    company_name: str
    role_title: Optional[str] = None


class EmailDraftRequest(BaseModel):
    recipient_name: str
    company_name: str
    role_title: str


class InterviewPrepRequest(BaseModel):
    role_title: str
    company_name: str
    job_description: Optional[str] = None
    focus_tech: Optional[List[str]] = None


class OfferAnalysisRequest(BaseModel):
    company_name: str
    role_title: str
    base_salary: float
    bonus: float = 0.0
    equity_annual_val: float = 0.0


class UpdateStatusRequest(BaseModel):
    status: str
    note: Optional[str] = None


@router.get("/status")
def get_career_status():
    """PWR-328: Career service status and candidate overview."""
    return career_powers.get_service_status()


@router.post("/scan")
def scan_job(request: JobScanRequest):
    """PWR-329: Job scan and ATS fit score calculation."""
    try:
        return career_powers.scan_job_listing(
            job_title=request.job_title,
            company_name=request.company_name,
            description=request.description,
            job_url=request.job_url
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume")
def generate_resume(request: ResumeRequest):
    """PWR-330: Tailored ATS resume generation."""
    try:
        return career_powers.generate_tailored_resume(
            job_title=request.job_title,
            company_name=request.company_name,
            target_keywords=request.target_keywords
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cover-letter")
def generate_cover_letter(request: CoverLetterRequest):
    """PWR-331: Tailored cover letter generation."""
    try:
        return career_powers.generate_cover_letter(
            job_title=request.job_title,
            company_name=request.company_name,
            key_challenges=request.key_challenges
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/company-research")
def research_company(request: CompanyResearchRequest):
    """PWR-332: Company research dossier."""
    try:
        return career_powers.research_company_brief(
            company_name=request.company_name,
            domain=request.domain
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts")
def find_contacts(request: ContactFinderRequest):
    """PWR-333: Contact discovery and outreach draft."""
    try:
        return career_powers.find_company_contacts(
            company_name=request.company_name,
            role_title=request.role_title
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/draft-email")
def draft_email(request: EmailDraftRequest):
    """PWR-334: Application email draft."""
    try:
        return career_powers.draft_application_email(
            recipient_name=request.recipient_name,
            company_name=request.company_name,
            role_title=request.role_title
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline")
def get_pipeline():
    """PWR-335: Application pipeline analytics and funnel stats."""
    return career_powers.analyze_application_pipeline()


@router.get("/applications")
def list_applications(status: Optional[str] = None):
    """Lists tracked job applications."""
    apps = career_powers.service.list_applications(status)
    return {"applications": [a.model_dump() for a in apps]}


@router.patch("/applications/{application_id}/status")
def update_application_status(application_id: str, request: UpdateStatusRequest):
    """Updates the status of a tracked application."""
    updated = career_powers.service.update_application_status(
        application_id=application_id,
        new_status=request.status,
        note=request.note
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Application not found")
    return updated.model_dump()


@router.post("/interview-prep")
def prepare_interview(request: InterviewPrepRequest):
    """PWR-336: Interview preparation, STAR questions, and red-flag checking."""
    try:
        return career_powers.interview_prep_and_red_flags(
            role_title=request.role_title,
            company_name=request.company_name,
            job_description=request.job_description,
            focus_tech=request.focus_tech
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offer-analysis")
def analyze_offer(request: OfferAnalysisRequest):
    """PWR-337: Compensation and salary-gap analysis."""
    try:
        return career_powers.analyze_offer_and_salary_gap(
            company_name=request.company_name,
            role_title=request.role_title,
            base_salary=request.base_salary,
            bonus=request.bonus,
            equity_annual_val=request.equity_annual_val
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

