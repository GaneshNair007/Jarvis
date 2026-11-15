from __future__ import annotations

import json

import pytest

from jarvis.career.internship_automation import InternshipAutomation, InternshipSettings


def make_service(tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF test fixture")
    profile = tmp_path / "candidate_profile.json"
    profile.write_text(json.dumps({
        "full_name": "Ganesh Nair",
        "email": "ganesh@example.com",
        "location": "Pune, Maharashtra, India",
        "education": "B.Tech Artificial Intelligence & Machine Learning, SIT Pune",
        "graduation_year": "2029",
        "skills": ["Python", "SQL", "Pandas", "Scikit-learn"],
        "projects": ["Signal Atlas", "CORTEX Cloud Autopilot"],
        "target_roles": ["AI/ML Intern", "Python Developer Intern"],
        "resume_path": str(resume),
    }), encoding="utf-8")
    settings = InternshipSettings(
        profile_path=profile,
        database_path=tmp_path / "internships.sqlite3",
        approval_secret="test-secret-key-that-is-long-enough-for-hmac-approval",
        approval_ttl_seconds=900,
    )
    return InternshipAutomation(settings)


def test_rejects_non_https_and_unsupported_source(tmp_path):
    service = make_service(tmp_path)
    with pytest.raises(ValueError):
        service.add_manual_opportunity({"source": "linkedin_manual", "company": "Acme", "title": "AI Intern", "url": "http://example.com/job"})
    with pytest.raises(ValueError):
        service.add_manual_opportunity({"source": "unknown", "company": "Acme", "title": "AI Intern", "url": "https://example.com/job"})


def test_prepare_requires_profile_and_manual_review(tmp_path):
    service = make_service(tmp_path)
    opportunity = service.add_manual_opportunity({
        "source": "company_careers",
        "company": "Acme",
        "title": "Python Intern",
        "url": "https://example.com/careers/python-intern",
        "description": "Internship for students. Python, SQL and Pandas.",
    })
    prepared = service.prepare_application(opportunity["id"])
    assert prepared["status"] == "PENDING_REVIEW"
    assert prepared["draft"]["generated_from_verified_profile_fields_only"] is True
    assert prepared["notice"].endswith("No form has been submitted.")
    assert "full-time" not in prepared["draft"]["cover_letter"].lower()


def test_approval_is_bound_to_exact_draft_and_expires(tmp_path):
    service = make_service(tmp_path)
    opportunity = service.add_manual_opportunity({
        "source": "startup_website",
        "company": "Acme",
        "title": "AI/ML Intern",
        "url": "https://example.com/jobs/aiml-intern",
        "description": "Internship for undergraduate students. Python and machine learning.",
    })
    prepared = service.prepare_application(opportunity["id"])
    with pytest.raises(PermissionError):
        service.approve_application(prepared["application_id"], "wrong-hash", True)
    with pytest.raises(PermissionError):
        service.approve_application(prepared["application_id"], prepared["review_hash"], False)
    approved = service.approve_application(prepared["application_id"], prepared["review_hash"], True)
    assert approved["status"] == "APPROVED_FOR_MANUAL_SUBMISSION"
    assert service.verify_submission_approval(
        prepared["application_id"], approved["one_time_approval_token"]
    )
    recorded = service.mark_manually_submitted(
        prepared["application_id"], approved["one_time_approval_token"],
        "Employer confirmation page displayed; user verified", True
    )
    assert recorded["status"] == "MANUALLY_SUBMITTED_CONFIRMED_BY_USER"
    assert "JARVIS did not submit" in recorded["recording"]
    assert not service.verify_submission_approval(
        prepared["application_id"], approved["one_time_approval_token"]
    )
    assert not service.verify_submission_approval(prepared["application_id"], "tampered-token")


def test_status_reports_missing_profile_without_false_success(tmp_path):
    settings = InternshipSettings(
        profile_path=tmp_path / "missing.json",
        database_path=tmp_path / "empty.sqlite3",
        approval_secret="test-secret-key-that-is-long-enough-for-hmac-approval",
    )
    service = InternshipAutomation(settings)
    status = service.status()
    assert status["profile_configured"] is False
    assert status["profile_error"]
    assert status["opportunities"] == 0



def test_manual_import_deduplicates_same_source_url(tmp_path):
    service = make_service(tmp_path)
    payload = {
        "source": "company_careers",
        "company": "Acme",
        "title": "Python Intern",
        "url": "https://example.com/jobs/python-intern",
        "description": "Student internship with Python.",
    }
    first = service.add_manual_opportunity(payload)
    second = service.add_manual_opportunity(payload)
    assert first["id"] == second["id"]
    assert len(service.list_opportunities(limit=20)) == 1



def test_tampered_draft_cannot_be_approved(tmp_path):
    service = make_service(tmp_path)
    opportunity = service.add_manual_opportunity({
        "source": "company_careers",
        "company": "Acme",
        "title": "Python Intern",
        "url": "https://example.com/jobs/python-intern",
        "description": "Student internship with Python.",
    })
    prepared = service.prepare_application(opportunity["id"])
    with service._connect() as db:
        row = db.execute("SELECT draft_json FROM applications WHERE id=?", (prepared["application_id"],)).fetchone()
        altered = json.loads(row["draft_json"])
        altered["candidate_name"] = "Altered Name"
        db.execute("UPDATE applications SET draft_json=? WHERE id=?",
                   (json.dumps(altered), prepared["application_id"]))
    with pytest.raises(PermissionError, match="Stored draft changed"):
        service.approve_application(prepared["application_id"], prepared["review_hash"], True)
