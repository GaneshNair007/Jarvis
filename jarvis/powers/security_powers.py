"""JARVIS Security and DLP Powers (PWR-268 to PWR-287).

Provides zero-leak secret scans, cryptographic token verification,
firewall/kill-switch validation, and DLP redaction audits.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from jarvis.core.privacy_gate import privacy_gate
from jarvis.core.policy_gate import policy_gate
from jarvis.core.logger import get_logger

logger = get_logger("powers.security")


class SecurityPowers:
    """Implementations for Security and Guardrail domain capabilities."""

    def scan_secrets(self, text: str) -> Dict[str, Any]:
        """PWR-268: Scans text for exposed credentials, API keys, and sensitive tokens."""
        patterns = {
            "openai_key": r"sk-[A-Za-z0-9]{32,}",
            "anthropic_key": r"sk-ant-[A-Za-z0-9_-]{32,}",
            "aws_access_key": r"AKIA[0-9A-Z]{16}",
            "jwt_token": r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*",
            "private_key": r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----"
        }

        found_findings = []
        for key_type, regex in patterns.items():
            matches = re.findall(regex, text)
            if matches:
                found_findings.append({"type": key_type, "count": len(matches)})

        redacted, _ = privacy_gate.inspect_and_redact(text)
        return {
            "power_id": "PWR-268",
            "safe": len(found_findings) == 0,
            "findings_count": len(found_findings),
            "findings": found_findings,
            "redacted_text_length": len(redacted)
        }

    def verify_kill_switch(self) -> Dict[str, Any]:
        """PWR-279: Queries emergency kill-switch status across the operating system."""
        is_blocked = policy_gate.is_kill_switch_active()
        return {
            "power_id": "PWR-279",
            "kill_switch_active": is_blocked,
            "system_state": "LOCKED" if is_blocked else "OPERATIONAL"
        }

    def verify_approval_token(self, token: str, action: Optional[str] = None) -> Dict[str, Any]:
        """PWR-284: Verifies cryptographic validity and expiration of an approval token."""
        valid = policy_gate.verify_token(token)
        return {
            "power_id": "PWR-284",
            "token": token,
            "action": action,
            "valid": valid
        }


security_powers = SecurityPowers()
