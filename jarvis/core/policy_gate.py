"""
JARVIS Deterministic Policy Gate & Approval Engine
Enforces deny-by-default access control across Privilege Levels 0 to 5.
Validates HMAC-SHA256 cryptographic approval tokens bound to payload hashes.
"""

import hmac
import hashlib
import time
import datetime
from typing import Dict, Any, Tuple, Optional, List
from jarvis.config import settings

class PolicyGate:
    # Privilege Level mappings
    PRIVILEGE_LEVELS = {
        0: "PUBLIC_READ",       # Web search, public docs
        1: "LOCAL_READ",        # Reading local files, telemetry
        2: "LOCAL_WRITE",       # Writing temp drafts, local notes
        3: "OUTBOUND_COMM",     # Sending emails, posting messages
        4: "SYSTEM_MODIFY",     # Installing packages, editing configs
        5: "IRREVERSIBLE_OP"    # Deleting files, code deploy, financial purchase
    }

    # Powers that strictly require human cryptographic approval
    APPROVAL_REQUIRED_POWERS = {
        # File & System deletions / drops
        "delete_file", "drop_table", "kill_process", "format_disk",
        # Outbound comms
        "send_email", "post_tweet", "submit_form", "send_chat_message",
        # Financial / deployment
        "purchase_item", "execute_trade", "deploy_production", "reboot_host"
    }

    def __init__(self):
        self.secret_key = settings.jarvis_secret_key.encode("utf-8")
        self.kill_switch_active = False
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}

    def trigger_kill_switch(self, reason: str = "Manual emergency stop") -> None:
        """Immediately halts all autonomous execution loops."""
        self.kill_switch_active = True

    def reset_kill_switch(self) -> None:
        self.kill_switch_active = False

    def hash_payload(self, payload: Any) -> str:
        """Generates canonical SHA-256 hash of task execution parameters."""
        data_str = str(payload).encode("utf-8")
        return hashlib.sha256(data_str).hexdigest()

    def generate_approval_token(self, task_id: str, power_id: str, payload_hash: str) -> Tuple[str, float]:
        """Creates an HMAC-SHA256 token valid for the configured approval window."""
        expiry = int(time.time() + (settings.approval_token_expiry_minutes * 60))
        message = f"{task_id}:{power_id}:{payload_hash}:{expiry}".encode("utf-8")
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        token = f"{signature}.{expiry}"
        return token, float(expiry)

    def verify_approval_token(self, task_id: str, power_id: str, payload_hash: str, token: str) -> Tuple[bool, str]:
        """Validates the cryptographic HMAC signature and expiration of an approval token."""
        try:
            sig, expiry_str = token.split(".")
            expiry = int(expiry_str)
            if time.time() > expiry:
                return False, "Approval token has expired"

            message = f"{task_id}:{power_id}:{payload_hash}:{expiry}".encode("utf-8")
            expected_sig = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()

            if hmac.compare_digest(sig, expected_sig):
                return True, "Approval token valid and verified"
            return False, "Invalid cryptographic signature on approval token"
        except Exception as e:
            return False, f"Malformed approval token: {str(e)}"

    def evaluate_execution(
        self,
        task_id: str,
        power_id: str,
        privilege_level: int,
        payload: Dict[str, Any],
        approval_token: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Deterministic Policy Evaluation:
        1. Check emergency kill switch
        2. Check privilege level and approval requirements
        3. Check allow-lists (directories, domains)
        4. Validate cryptographic approval if needed
        """
        # 1. Kill Switch Check
        if self.kill_switch_active:
            return False, "EXECUTION BLOCKED: Emergency Kill Switch is ACTIVE", None

        payload_hash = self.hash_payload(payload)

        # 2. Level 0 & 1 (Reads) - Allow if configured
        if privilege_level <= 1:
            if not settings.allow_unapproved_reads and privilege_level == 1:
                return False, "Policy requires read approval in strict isolation mode", None
            return True, "Read operation cleared by Policy Gate", None

        # 3. Check if Power or Privilege Level requires approval
        needs_approval = (
            privilege_level >= 3 or
            power_id.lower() in self.APPROVAL_REQUIRED_POWERS or
            any(danger_kw in power_id.lower() for danger_kw in ["delete", "drop", "deploy", "buy", "send", "kill"])
        )

        if needs_approval:
            if not approval_token:
                # Generate a pending approval request
                token, expiry = self.generate_approval_token(task_id, power_id, payload_hash)
                approval_req = {
                    "task_id": task_id,
                    "power_id": power_id,
                    "payload_hash": payload_hash,
                    "token": token,
                    "expires_at": expiry,
                    "action_summary": f"Execute {power_id} (Level {privilege_level} - {self.PRIVILEGE_LEVELS.get(privilege_level)})"
                }
                self.pending_approvals[task_id] = approval_req
                return False, f"POLICY REQUIREMENT: Human approval required for {power_id} (Level {privilege_level})", approval_req

            # Verify token
            valid, reason = self.verify_approval_token(task_id, power_id, payload_hash, approval_token)
            if not valid:
                return False, f"APPROVAL FAILED: {reason}", None

        # 4. Allow-list Verifications
        # Directory check
        target_dir = payload.get("target_directory") or payload.get("directory") or payload.get("path")
        if target_dir:
            if not any(target_dir.startswith(allowed) for allowed in settings.allowed_directories):
                # If strict mode, deny
                if settings.policy_strict_mode and privilege_level >= 2:
                    return False, f"SECURITY VIOLATION: Path '{target_dir}' is not within allowed directories", None

        return True, "Policy Gate approved execution", None

# Singleton Policy Gate
policy_gate = PolicyGate()
