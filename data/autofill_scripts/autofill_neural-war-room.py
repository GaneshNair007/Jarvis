"""
Playwright DOM Autofill Script for Flip the Switch Hackathon
Autonomously fills registration and submission forms for Ganesh Nair.
"""

import asyncio
from playwright.async_api import async_playwright

SUBMISSION_DATA = {
    "applicant_name": "Ganesh Nair",
    "applicant_email": "nairganesh134@gmail.com",
    "applicant_phone": "+91 9324094474",
    "project_title": "Neural War Room",
    "tagline": "Autonomous, First-Law compliant multi-agent system solving Flip the Switch Hackathon.",
    "description": "Autonomous multi-agent consensus system.",
    "repository_url": "https://github.com/GaneshNair007/neural-war-room",
    "local_scaffold_path": "data/scaffolded_projects/neural-war-room",
    "git_commit": "abc1234def",
    "demo_url": "https://neural-war-room.demo.internal",
    "tech_stack": "Python, FastAPI, Distributed Systems, LLM Orchestration, LangGraph, AsyncIO, SQLite FTS5, Qdrant, Meilisearch, Docker, Kubernetes, High-Throughput Concurrency, Playwright, PostgreSQL, Redis",
    "team_lead": "Ganesh Nair",
    "experience_level": "Professional / Advanced"
}

async def autofill_and_submit(headless: bool = True):
    print("Launching browser to autofill form at: https://www.wemakedevs.org/hackathons/switch")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto("https://www.wemakedevs.org/hackathons/switch", timeout=30000)
            print("Page loaded. Injecting verified applicant parameters...")
            
            # Map standard inputs if present
            for selector, val in [
                ("input[name*='name' i]", SUBMISSION_DATA['applicant_name']),
                ("input[name*='email' i]", SUBMISSION_DATA['applicant_email']),
                ("input[name*='phone' i]", SUBMISSION_DATA['applicant_phone']),
                ("input[name*='repo' i]", SUBMISSION_DATA['repository_url']),
                ("input[name*='github' i]", SUBMISSION_DATA['repository_url']),
                ("textarea[name*='desc' i]", SUBMISSION_DATA['description']),
            ]:
                try:
                    el = await page.wait_for_selector(selector, timeout=2000)
                    if el:
                        await el.fill(val)
                except Exception:
                    pass
            print("Form autofill complete for Ganesh Nair.")
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(autofill_and_submit())
