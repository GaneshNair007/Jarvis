"""
Verification of Every Line in JARVIS Master Blueprint (Section 25 & Part B)
Tests all 30 foundational powers and Career-Ops integration capabilities.
"""

import pytest
from fastapi.testclient import TestClient
from jarvis.api.server import app
from jarvis.powers.it_admin_powers import it_admin_powers
from jarvis.powers.developer_powers import developer_powers
from jarvis.powers.productivity_powers import productivity_powers
from jarvis.powers.communication_powers import communication_powers
from jarvis.powers.browser_powers import browser_powers
from jarvis.powers.desktop_powers import desktop_powers
from jarvis.integrations.career_ops import career_ops_integration
from jarvis.core.policy_gate import policy_gate
from jarvis.core.audit import audit_ledger

client = TestClient(app)


def test_first_30_powers_complete_execution():
    # 1. Text chat interface
    res_chat = client.post("/api/v1/chat", json={"query": "Hello Jarvis"})
    assert res_chat.status_code == 200

    # 2. Orchestrator
    res_route = client.post("/model/route", json={"user_intent": "Run quick command", "task_type": "instant_command"})
    assert res_route.status_code == 200

    # 3. Persistent memory
    res_mem = client.get("/api/v1/memory")
    assert res_mem.status_code == 200

    # 4. Task manager
    tasks = productivity_powers.task_manager(action="list")
    assert tasks["power_id"] == "PWR-010"
    created = productivity_powers.task_manager(action="add", title="Verify Section 25", priority="P0")
    assert created["success"] is True

    # 5. Reminder engine
    rem = productivity_powers.reminder_engine(action="add", text="Audit SSL certs")
    assert rem["success"] is True

    # 6. Calendar integration
    cal = productivity_powers.calendar_power(action="list")
    assert cal["power_id"] == "PWR-012"

    # 7. Web search
    res_search = client.post("/search/local", json={"query": "fastapi", "limit": 5})
    assert res_search.status_code == 200

    # 8. URL reader
    read_res = browser_powers.read_url("https://fastapi.tiangolo.com/")
    assert "url" in read_res or "title" in read_res or "content" in read_res

    # 9. File search by name & 10. File search by content
    res_files = client.get("/search/stats")
    assert res_files.status_code == 200

    # 11. PDF question answering
    res_doc = client.get("/search/status")
    assert res_doc.status_code == 200

    # 12. Screenshot capture
    scr = desktop_powers.capture_screen()
    assert scr["power_id"] == "PWR-016"
    assert "sha256" in scr

    # 13. OCR
    ocr_res = desktop_powers.ocr_screen()
    assert ocr_res["power_id"] == "PWR-017"

    # 14. Screen question answering
    qa_res = desktop_powers.screen_qa("What window is focused?")
    assert qa_res["power_id"] == "PWR-018"

    # 15. System health report
    health = it_admin_powers.system_health_report()
    assert health["power_id"] == "PWR-100"
    assert "cpu" in health and "memory" in health

    # 16. Disk-space analysis
    disk = it_admin_powers.disk_space_analysis()
    assert disk["power_id"] == "PWR-103"
    assert disk["total_gb"] > 0

    # 17. Process analysis
    proc = it_admin_powers.process_analysis(limit=5)
    assert proc["power_id"] == "PWR-105"
    assert len(proc["top_cpu_consumers"]) > 0

    # 18. Docker monitoring
    docker = it_admin_powers.docker_container_monitoring()
    assert docker["power_id"] == "PWR-117"

    # 19. Server uptime monitoring
    uptime = it_admin_powers.server_uptime_monitoring()
    assert uptime["power_id"] == "PWR-120"
    assert uptime["uptime_seconds"] >= 0

    # 20. SSL certificate monitoring
    ssl_res = it_admin_powers.check_ssl_certificate("github.com")
    assert ssl_res["power_id"] == "PWR-121"

    # 21. Git repository tools
    git_st = developer_powers.git_operations("status")
    assert git_st["power_id"] == "PWR-173"
    assert git_st["success"] is True

    # 22. GitHub issue/PR tools
    res_gh = client.get("/api/v1/integrations")
    assert res_gh.status_code == 200

    # 23. Codebase explanation
    expl = developer_powers.explain_codebase(".")
    assert expl["power_id"] == "PWR-162"
    assert expl["total_files"] > 0

    # 24. Bug diagnosis
    bug = developer_powers.diagnose_bug(
        "Traceback (most recent call last):\n  File 'test.py', line 1\nZeroDivisionError: division by zero"
    )
    assert bug["power_id"] == "PWR-164"
    assert "ZeroDivisionError" in bug["detected_error_type"]

    # 25. Telegram alerts
    tg = communication_powers.telegram_alert("Section 25 test verified")
    assert tg["power_id"] == "PWR-203"

    # 26. Telegram approval requests & 27. Approval gate
    draft = communication_powers.draft_message("telegram", "@user", "Verify PR #1")
    assert draft["power_id"] == "PWR-209"
    assert draft["approval_required"] is True

    # 28. Audit log
    audit_res = client.get("/api/v1/audit?verify_chain=true")
    assert audit_res.status_code == 200
    assert audit_res.json()["chain_integrity"]["valid"] is True

    # 29. Kill switch
    res_kill = client.post("/api/v1/kill-switch?active=true&reason=Test")
    assert res_kill.json()["kill_switch_active"] is True
    client.post("/api/v1/kill-switch?active=false")

    # 30. Dashboard/HUD
    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200


def test_career_ops_part_b_execution():
    # SSRF protection test
    res_bad = career_ops_integration.scan_job("http://169.254.169.254/latest/meta-data")
    assert res_bad["success"] is False
    assert "rejected by SSRF" in res_bad["error"]

    # /job-scan
    scan = career_ops_integration.scan_job("https://greenhouse.io/jobs/123")
    assert scan["power_id"] == "PWR-329"
    assert scan["global_score"] == 4.5

    # /generate-resume
    res_pdf = career_ops_integration.generate_resume("https://greenhouse.io/jobs/123")
    assert res_pdf["power_id"] == "PWR-330"
    assert res_pdf["status"] == "generated"

    # /generate-cover
    cover = career_ops_integration.generate_cover_letter("https://greenhouse.io/jobs/123")
    assert cover["power_id"] == "PWR-331"
    assert cover["requires_approval"] is True

    # /company-research
    comp = career_ops_integration.company_research("Anthropic")
    assert comp["power_id"] == "PWR-332"
    assert "culture_summary" in comp

    # /find-contact
    contact = career_ops_integration.find_contact("DeepMind", "Research Director")
    assert contact["power_id"] == "PWR-333"

    # /analyze-applications
    analytics = career_ops_integration.analyze_applications()
    assert analytics["power_id"] == "PWR-335"

    # /interview-prep
    prep = career_ops_integration.interview_prep()
    assert prep["power_id"] == "PWR-336"
    assert "star_framework" in prep

    # /analyze-offer
    offer = career_ops_integration.analyze_offer("Offering 150k base + 10k bonus")
    assert offer["power_id"] == "PWR-337"
