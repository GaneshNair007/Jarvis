"""
JARVIS Privacy Gate & Data Loss Prevention (DLP)
Inspects text and attachments before routing, redacting secrets, credentials,
tokens, credit cards, and PII. Ensures unredacted private data never leaks to cloud models.
"""

import re
from typing import Dict, List, Tuple, Any

class PrivacyGate:
    # Pattern definitions for sensitive data
    PATTERNS = {
        "api_key_openai": (r"\bsk-[a-zA-Z0-9]{20,48}\b", "[REDACTED_OPENAI_KEY]"),
        "api_key_anthropic": (r"\bsk-ant-[a-zA-Z0-9_\-]{20,80}\b", "[REDACTED_CLAUDE_KEY]"),
        "api_key_aws": (r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED_AWS_KEY]"),
        "api_key_github": (r"\bgh[pousr]_[a-zA-Z0-9]{36,255}\b", "[REDACTED_GITHUB_TOKEN]"),
        "private_key": (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
        "credit_card": (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b", "[REDACTED_CREDIT_CARD]"),
        "otp": (r"(?i)\b(?:otp|code|passcode|pin)[:\s=]+([0-9]{4,8})\b", "[REDACTED_OTP]"),
        "password_assign": (r"(?i)\b(?:password|passwd|pwd|secret)[:\s=]+(['\"][^'\"]+['\"]|\S+)", "[REDACTED_PASSWORD]"),
        "jwt_token": (r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b", "[REDACTED_JWT]"),
        "ssn": (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
    }

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    def inspect_and_redact(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Scans text for sensitive patterns, redacting matched entities and returning
        the sanitized string along with an audit list of redactions made.
        """
        if not text:
            return "", []

        redacted_text = text
        findings: List[Dict[str, Any]] = []

        for category, (pattern, replacement) in self.PATTERNS.items():
            matches = list(re.finditer(pattern, redacted_text))
            if matches:
                # Store redacted count
                findings.append({
                    "category": category,
                    "count": len(matches),
                    "replacement": replacement
                })
                redacted_text = re.sub(pattern, replacement, redacted_text)

        return redacted_text, findings

    def contains_sensitive_data(self, text: str) -> bool:
        """Returns True if any unredacted sensitive entity is detected."""
        if not text:
            return False
        for category, (pattern, _) in self.PATTERNS.items():
            if re.search(pattern, text):
                return True
        return False

    def can_route_to_cloud(self, text: str, requires_cloud_consent: bool = False, has_consent: bool = False) -> Tuple[bool, str]:
        """
        Determines whether a payload is safe to transmit to an external cloud model.
        Returns (allowed: bool, reason: str).
        """
        if self.contains_sensitive_data(text):
            return False, "Payload contains unredacted credentials or sensitive tokens"

        if requires_cloud_consent and not has_consent:
            return False, "Task requires explicit user consent for external cloud routing"

        return True, "Payload cleared by Privacy Gate"

    def minimize_context(self, context: str, max_chars: int = 12000) -> str:
        """
        Reduces token footprint by pruning middle segments of long documents
        while preserving start directives and terminal conclusions.
        """
        if not context or len(context) <= max_chars:
            return context

        head = context[: max_chars // 2]
        tail = context[- (max_chars // 2) :]
        return f"{head}\n\n[... Context Minimized by Jarvis Privacy Gate ({len(context) - max_chars} characters omitted) ...]\n\n{tail}"

# Singleton Privacy Gate
privacy_gate = PrivacyGate()
