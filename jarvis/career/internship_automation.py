"""Local-first internship discovery and application-preparation service.

Only public Greenhouse, Lever and Ashby job-board endpoints are queried.
LinkedIn, Internshala and Wellfound are manual-review/import sources.
No application is submitted by discovery or drafting.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


ALLOWED_MANUAL_SOURCES = {"company_careers", "startup_website", "wellfound", "internshala", "linkedin_manual"}
ATS_PROVIDERS = {"greenhouse", "lever", "ashby"}


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _safe_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Only absolute HTTPS job URLs are accepted")
    if parsed.username or parsed.password:
        raise ValueError("Credential-bearing URLs are not accepted")
    return value


@dataclass
class InternshipSettings:
    profile_path: Path = Path(os.getenv("JARVIS_CANDIDATE_PROFILE", "data/candidate_profile.json"))
    database_path: Path = Path(os.getenv("JARVIS_INTERNSHIP_DB", "data/internship_applications.sqlite3"))
    approval_secret: str = os.getenv("JARVIS_SECRET_KEY", "")
    approval_ttl_seconds: int = 900

    @classmethod
    def from_env(cls) -> "InternshipSettings":
        # Reuse JARVIS typed .env configuration instead of reading secrets
        # directly from os.environ (Pydantic also loads the project .env).
        from jarvis.config import PROJECT_ROOT, settings as jarvis_settings
        return cls(
            profile_path=Path(os.getenv("JARVIS_CANDIDATE_PROFILE", str(PROJECT_ROOT / "data" / "candidate_profile.json"))),
            database_path=Path(os.getenv("JARVIS_INTERNSHIP_DB", str(jarvis_settings.data_dir / "internship_applications.sqlite3"))),
            approval_secret=os.getenv("JARVIS_SECRET_KEY") or jarvis_settings.jarvis_secret_key,
            approval_ttl_seconds=int(os.getenv("JARVIS_INTERNSHIP_APPROVAL_TTL", "900")),
        )


class InternshipAutomation:
    """Discover, score, draft and gate internship applications for human review."""

    def __init__(self, settings: InternshipSettings | None = None):
        self.settings = settings or InternshipSettings.from_env()
        self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.settings.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT,
                company TEXT NOT NULL, title TEXT NOT NULL, location TEXT,
                url TEXT NOT NULL, description TEXT, employment_type TEXT,
                created_at REAL NOT NULL, raw_json TEXT NOT NULL,
                UNIQUE(source, external_id, url))""")
            db.execute("""CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL,
                status TEXT NOT NULL, fit_score REAL NOT NULL,
                draft_json TEXT NOT NULL, review_hash TEXT NOT NULL,
                approval_hash TEXT, approval_expires REAL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL,
                FOREIGN KEY(opportunity_id) REFERENCES opportunities(id))""")

    def load_profile(self) -> dict[str, Any]:
        path = self.settings.profile_path
        if not path.exists():
            raise FileNotFoundError(
                f"Candidate profile is not configured. Create {path} from the resume and verify every field."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"full_name", "email", "location", "education", "graduation_year", "skills", "resume_path"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"Candidate profile missing required fields: {', '.join(missing)}")
        if not isinstance(data["skills"], list) or not all(isinstance(x, str) for x in data["skills"]):
            raise ValueError("Candidate profile skills must be a list of strings")
        resume = Path(data["resume_path"]).expanduser()
        if not resume.is_file():
            raise ValueError("Configured resume_path does not point to an existing file")
        return data

    def status(self) -> dict[str, Any]:
        profile_ok = False
        profile_error = None
        try:
            self.load_profile()
            profile_ok = True
        except Exception as exc:
            profile_error = str(exc)
        with self._connect() as db:
            opportunities = db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
            pending = db.execute("SELECT COUNT(*) FROM applications WHERE status='PENDING_REVIEW'").fetchone()[0]
            approved = db.execute("SELECT COUNT(*) FROM applications WHERE status='APPROVED_FOR_MANUAL_SUBMISSION'").fetchone()[0]
        ollama_ready = False
        ollama_model = None
        try:
            from jarvis.config import settings as jarvis_settings
            ollama_model = jarvis_settings.ollama_default_model
            response = httpx.get(jarvis_settings.ollama_base_url.rstrip("/") + "/api/tags", timeout=1.5)
            response.raise_for_status()
            available = [item.get("name") for item in response.json().get("models", [])]
            ollama_ready = any(name == ollama_model or str(name).startswith(ollama_model + ":") for name in available)
        except Exception:
            pass
        return {
            "service": "internship-automation",
            "profile_configured": profile_ok,
            "profile_error": profile_error,
            "database": str(self.settings.database_path),
            "opportunities": opportunities,
            "pending_review": pending,
            "approved_for_manual_submission": approved,
            "submission_mode": "human-approved; manual final submission",
            "supported_ats": sorted(ATS_PROVIDERS),
            "manual_sources": sorted(ALLOWED_MANUAL_SOURCES),
            "ollama": {"available": ollama_ready, "model": ollama_model, "scope": "local-only job-description summaries; never invents candidate facts"},
        }

    @staticmethod
    def _normalize_job(provider: str, item: dict[str, Any], board: str) -> dict[str, Any] | None:
        if provider == "greenhouse":
            title = item.get("title")
            url = item.get("absolute_url")
            company = board
            desc = _clean_text(item.get("content", ""))
            external_id = str(item.get("id", ""))
            location = (item.get("location") or {}).get("name", "")
        elif provider == "lever":
            title = item.get("text")
            url = item.get("hostedUrl") or item.get("applyUrl")
            company = board
            desc = _clean_text(" ".join([
                item.get("descriptionPlain", ""), item.get("additional", {}).get("description", ""),
                " ".join(x.get("content", "") for x in item.get("lists", []) if isinstance(x, dict))
            ]))
            external_id = str(item.get("id", ""))
            categories = item.get("categories") or {}
            location = categories.get("location", "")
        else:
            title = item.get("title")
            url = item.get("jobUrl") or item.get("applyUrl")
            company = board
            desc = _clean_text(item.get("descriptionPlain") or item.get("descriptionHtml") or "")
            external_id = str(item.get("id", ""))
            location = item.get("location", "")
        if not title or not url:
            return None
        try:
            url = _safe_url(url)
        except ValueError:
            return None
        return {
            "source": provider, "external_id": external_id or url, "company": company,
            "title": str(title), "location": str(location or ""), "url": url,
            "description": desc, "employment_type": "internship" if "intern" in str(title).lower() else "",
            "raw": item,
        }

    async def discover(self, boards: list[dict[str, str]]) -> dict[str, Any]:
        """Fetch public job listings from explicitly configured ATS board identifiers."""
        found: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={"User-Agent": "JARVIS-CareerRadar/1.0"}) as client:
            for board_cfg in boards:
                provider = str(board_cfg.get("provider", "")).lower()
                board = str(board_cfg.get("board", "")).strip()
                if provider not in ATS_PROVIDERS or not board or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", board):
                    errors.append({"board": board, "error": "Unsupported provider or invalid board identifier"})
                    continue
                if provider == "greenhouse":
                    endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
                elif provider == "lever":
                    endpoint = f"https://api.lever.co/v0/postings/{board}?mode=json"
                else:
                    endpoint = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
                try:
                    response = await client.get(endpoint)
                    response.raise_for_status()
                    payload = response.json()
                    items = payload.get("jobs", []) if provider == "greenhouse" else (
                        payload if provider == "lever" else payload.get("jobs", [])
                    )
                    for item in items if isinstance(items, list) else []:
                        job = self._normalize_job(provider, item, board)
                        if job:
                            found.append(job)
                except Exception as exc:
                    errors.append({"board": board, "error": f"{type(exc).__name__}: {exc}"})
        saved = self._save_opportunities(found)
        return {"discovered": len(found), "saved_or_updated": saved, "errors": errors}

    def add_manual_opportunity(self, data: dict[str, Any]) -> dict[str, Any]:
        source = str(data.get("source", "")).lower()
        if source not in ALLOWED_MANUAL_SOURCES:
            raise ValueError(f"Source must be one of: {', '.join(sorted(ALLOWED_MANUAL_SOURCES))}")
        job = {
            "source": source, "external_id": str(data.get("external_id") or uuid.uuid4().hex),
            "company": str(data.get("company", "")).strip(), "title": str(data.get("title", "")).strip(),
            "location": str(data.get("location", "")).strip(), "url": _safe_url(str(data.get("url", ""))),
            "description": str(data.get("description", "")).strip(),
            "employment_type": str(data.get("employment_type", "")), "raw": {"manual_import": True},
        }
        if not job["company"] or not job["title"]:
            raise ValueError("Company and title are required")
        self._save_opportunities([job])
        return self.list_opportunities(limit=1, query=job["title"])[0]

    def _save_opportunities(self, jobs: list[dict[str, Any]]) -> int:
        saved = 0
        with self._connect() as db:
            for job in jobs:
                db.execute("""INSERT INTO opportunities
                    (id,source,external_id,company,title,location,url,description,employment_type,created_at,raw_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source,external_id,url) DO UPDATE SET
                    title=excluded.title,location=excluded.location,description=excluded.description,raw_json=excluded.raw_json""",
                    (uuid.uuid4().hex, job["source"], job["external_id"], job["company"], job["title"],
                     job["location"], job["url"], job["description"], job["employment_type"], time.time(),
                     json.dumps(job["raw"], ensure_ascii=False)))
                saved += 1
        return saved

    def list_opportunities(self, limit: int = 100, query: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        sql = "SELECT * FROM opportunities"
        params: list[Any] = []
        if query:
            sql += " WHERE title LIKE ? OR company LIKE ? OR description LIKE ?"
            term = f"%{query}%"
            params.extend([term, term, term])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._score_row(dict(row)) for row in rows]

    def status(self) -> dict[str, Any]:
        profile_ready = False
        profile_error = None
        try:
            self.load_profile()
            profile_ready = True
        except Exception as exc:
            profile_error = str(exc)
        with self._connect() as db:
            opportunity_count = db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
            app_rows = db.execute("SELECT status, COUNT(*) AS count FROM applications GROUP BY status").fetchall()
        return {
            "service": "internship-automation",
            "profile_configured": profile_ready,
            "profile_error": profile_error,
            "database": str(self.settings.database_path),
            "opportunities": opportunity_count,
            "applications_by_status": {row["status"]: row["count"] for row in app_rows},
            "submission_mode": "human approval required; external final submission remains manual",
            "supported_ats": sorted(ATS_PROVIDERS),
            "manual_review_sources": sorted(ALLOWED_MANUAL_SOURCES),
        }

    def _score_row(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            profile = self.load_profile()
        except Exception:
            row.update({"fit_score": None, "matched_skills": [], "missing_skills": [], "eligibility": "PROFILE_NOT_CONFIGURED"})
            return row
        text = " ".join([row["title"], row["description"], row["location"]]).lower()
        skills = [s for s in profile["skills"] if s.lower() in text]
        missing = [s for s in profile["skills"] if s.lower() not in text]
        role_terms = [x.lower() for x in profile.get("target_roles", [])]
        role_match = any(term in row["title"].lower() for term in role_terms) if role_terms else False
        score = min(100.0, round((len(skills) / max(1, len(profile["skills"])) * 75) + (25 if role_match else 0), 1))
        row.update({"fit_score": score, "matched_skills": skills, "missing_skills": missing,
                    "eligibility": "REVIEW_REQUIRED", "score_type": "keyword_alignment_not_selection_probability"})
        return row

    def prepare_application(self, opportunity_id: str) -> dict[str, Any]:
        profile = self.load_profile()
        with self._connect() as db:
            row = db.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
            if not row:
                raise KeyError("Opportunity not found")
            job = dict(row)
            scored = self._score_row(job)
            if scored.get("fit_score") is None:
                raise ValueError("Candidate profile is not ready")
            draft = {
                "candidate_name": profile["full_name"], "candidate_email": profile["email"],
                "candidate_location": profile["location"], "education": profile["education"],
                "graduation_year": str(profile["graduation_year"]),
                "skills": profile["skills"], "projects": profile.get("projects", []),
                "resume_path": profile["resume_path"], "job_title": job["title"],
                "company": job["company"], "job_url": job["url"],
                "cover_letter": (
                    f"Dear Hiring Team,\n\nI am applying for the {job['title']} opportunity at {job['company']}. "
                    f"I am currently pursuing {profile['education']} and am interested in applying my skills in "
                    f"{', '.join(profile['skills'][:6])}. My relevant project experience includes "
                    f"{'; '.join(profile.get('projects', [])[:3]) or 'the projects listed in my attached resume'}. "
                    "I would welcome the opportunity to discuss how I can contribute while continuing to learn.\n\n"
                    "Best regards,\n" + profile["full_name"]
                ),
                "answers_require_candidate_review": True,
                "generated_from_verified_profile_fields_only": True,
            }
            review_hash = hashlib.sha256(json.dumps(draft, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            app_id = uuid.uuid4().hex
            now = time.time()
            db.execute("""INSERT INTO applications
                (id,opportunity_id,status,fit_score,draft_json,review_hash,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (app_id, opportunity_id, "PENDING_REVIEW", scored["fit_score"],
                 json.dumps(draft, ensure_ascii=False), review_hash, now, now))
        return {"application_id": app_id, "status": "PENDING_REVIEW", "fit_score": scored["fit_score"],
                "review_hash": review_hash, "draft": draft,
                "notice": "Review every field and document. No form has been submitted."}

    def list_applications(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM applications"
        params: list[Any] = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT 200"
        with self._connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [{**dict(r), "draft": json.loads(r["draft_json"]), "approval_hash": None} for r in rows]

    def approve_application(self, application_id: str, reviewed_hash: str, confirm: bool) -> dict[str, Any]:
        if confirm is not True:
            raise PermissionError("Explicit human confirmation is required")
        secret = self.settings.approval_secret
        if len(secret) < 32 or secret == "dev_secret_key_change_in_production_32b":
            raise RuntimeError("Set a unique JARVIS_SECRET_KEY of at least 32 characters before enabling application approvals")
        with self._connect() as db:
            row = db.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
            if not row:
                raise KeyError("Application not found")
            if row["status"] != "PENDING_REVIEW":
                raise ValueError("Only pending applications can be approved")
            if not hmac.compare_digest(row["review_hash"], reviewed_hash):
                raise PermissionError("Review hash mismatch: draft changed or user approved stale content")
            expires = int(time.time() + self.settings.approval_ttl_seconds)
            nonce = secrets.token_urlsafe(24)
            message = f"{application_id}:{reviewed_hash}:{expires}:{nonce}".encode()
            signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
            token = f"{expires}.{nonce}.{signature}"
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            db.execute("""UPDATE applications SET status=?,approval_hash=?,approval_expires=?,updated_at=? WHERE id=?""",
                       ("APPROVED_FOR_MANUAL_SUBMISSION", token_hash, expires, time.time(), application_id))
        return {"application_id": application_id, "status": "APPROVED_FOR_MANUAL_SUBMISSION",
                "one_time_approval_token": token, "expires_at": expires,
                "next_step": "Use the approved draft to complete the employer form yourself. JARVIS has not submitted it."}

    def verify_submission_approval(self, application_id: str, token: str) -> bool:
        with self._connect() as db:
            row = db.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
        if not row or row["status"] != "APPROVED_FOR_MANUAL_SUBMISSION" or not row["approval_hash"]:
            return False
        if row["approval_expires"] is None or time.time() > row["approval_expires"]:
            return False
        return hmac.compare_digest(row["approval_hash"], hashlib.sha256(token.encode()).hexdigest())


internship_automation = InternshipAutomation()
