"""
JARVIS Communication Specialist Agent
PDF Spec: Multi-Agent & Orchestration — Outbound Communication & Messaging

Executes real communication and email operations:
- Deterministic RFC 822 / MIME (.eml) email drafting with outbox storage
- Cryptographic SHA-256 draft integrity
- Truthful IMAP inbox scanning (honest DISCONNECTED status when unconfigured)
- Tier-2 gated sending and audit trail recording
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from jarvis.agents.base import AgentContext, AgentResult, AgentTask, BaseSpecialistAgent
from jarvis.core.logger import get_logger
from jarvis.powers.email_powers import EmailPowers, email_powers

logger = get_logger("agents.communication")


class CommunicationAgent(BaseSpecialistAgent):
    """
    Specialist agent for communications, email drafting, outbox management,
    truthful inbox scanning, and policy-gated sending.
    """

    name: str = "CommunicationAgent"
    role: str = "communication"
    permitted_tools: List[str] = [
        "email_draft",
        "email_outbox_read",
        "email_scan_inbox",
        "email_send",
        "contact_lookup",
        "email",
    ]

    def __init__(self, powers: Optional[EmailPowers] = None):
        self._powers = powers or email_powers

    def draft_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_addr: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        outbox_dir: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """
        Drafts an RFC 822 .eml message into the outbox.
        Safely validates recipient format without raising unhandled exceptions.
        """
        return self._powers.draft_email(
            to=to,
            subject=subject,
            body=body,
            from_addr=from_addr,
            cc=cc,
            bcc=bcc,
            outbox_dir=outbox_dir,
        )

    def scan_inbox(
        self,
        inbox_dir: Optional[str | Path] = None,
        query: str = "opportunity OR offer OR interview OR internship OR hackathon",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Truthfully scans inbox or reports honest DISCONNECTED status without credentials.
        Never fabricates synthetic mock messages.
        """
        return self._powers.scan_inbox_for_opportunities(
            inbox_dir=inbox_dir,
            query=query,
            limit=limit,
        )

    def send_email(
        self,
        draft_path: str,
        task_id: str = "",
        approval_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sends an email draft strictly gated behind Tier-2 cryptographic sign-off."""
        return self._powers.send_email(
            draft_path=draft_path,
            task_id=task_id,
            approval_token=approval_token,
        )

    def list_outbox(self, outbox_dir: Optional[str | Path] = None) -> Dict[str, Any]:
        """Lists pending email drafts currently in the outbox."""
        return self._powers.list_outbox(outbox_dir=outbox_dir)

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Executes assigned communication task using permitted tools only."""
        start = time.time()
        params = task.parameters
        goal = (task.goal or "").lower()
        tools_used: List[str] = []
        output: Any = None
        status = "SUCCESS"
        error: Optional[str] = None

        try:
            if "scan" in goal or "scan" in params or "inbox" in goal:
                tools_used.append("email_scan_inbox")
                output = self.scan_inbox(
                    inbox_dir=params.get("inbox_dir"),
                    query=params.get("query", "opportunity"),
                    limit=int(params.get("limit", 10)),
                )
            elif "send" in goal or "send" in params:
                tools_used.append("email_send")
                output = self.send_email(
                    draft_path=params.get("draft_path", ""),
                    task_id=task.task_id,
                    approval_token=params.get("approval_token"),
                )
            elif "outbox" in goal or "list_outbox" in params:
                tools_used.append("email_outbox_read")
                output = self.list_outbox(outbox_dir=params.get("outbox_dir"))
            else:
                tools_used.append("email_draft")
                output = self.draft_email(
                    to=params.get("to", "recipient@example.com"),
                    subject=params.get("subject", task.goal),
                    body=params.get("body", "Notification from JARVIS"),
                    cc=params.get("cc"),
                    bcc=params.get("bcc"),
                    outbox_dir=params.get("outbox_dir"),
                )

            duration_ms = round((time.time() - start) * 1000, 2)
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status=status,
                output=output,
                evidence={"tools": tools_used, "goal": task.goal},
                tools_used=tools_used,
                duration_ms=duration_ms,
                error=error,
            )
        except Exception as exc:
            duration_ms = round((time.time() - start) * 1000, 2)
            logger.error(f"CommunicationAgent.execute failed: {exc}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status="FAILED",
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
            )


# ── Singletons & Aliases ─────────────────────────────────────────────────────
communication_agent = CommunicationAgent()
agent = communication_agent

__all__ = ["CommunicationAgent", "communication_agent", "agent"]
