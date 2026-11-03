"""
JARVIS Deterministic Policy Gate & Approval Engine
Enforces deny-by-default access control across Privilege Levels 0 to 5.
Validates HMAC-SHA256 cryptographic approval tokens bound to payload hashes.
"""

import hmac
import hashlib
import time
import uuid
import datetime
from typing import Dict, Any, Tuple, Optional, List, Set
from jarvis.config import settings


class PolicyGate:
    # Privilege Level mappings
    PRIVILEGE_LEVELS = {
        0: "PUBLIC_READ",  # Web search, public docs
        1: "LOCAL_READ",  # Reading local files, telemetry
        2: "LOCAL_WRITE",  # Writing temp drafts, local notes
        3: "OUTBOUND_COMM",  # Sending emails, posting messages
        4: "SYSTEM_MODIFY",  # Installing packages, editing configs
        5: "IRREVERSIBLE_OP",  # Deleting files, code deploy, financial purchase
    }

    # Powers that strictly require human cryptographic approval
    APPROVAL_REQUIRED_POWERS = {
        # File & System deletions / drops
        "delete_file",
        "drop_table",
        "drop_database",
        "kill_process",
        "format_disk",
        "wipe_system",
        # Outbound comms
        "send_email",
        "post_tweet",
        "submit_form",
        "send_chat_message",
        # Financial / deployment / lifecycle
        "purchase_item",
        "execute_trade",
        "trade_crypto",
        "mint_nft",
        "deploy_production",
        "reboot_host",
        "shutdown_host",
    }

    CRITICAL_POWERS = {
        "format_disk",
        "drop_database",
        "wipe_system",
        "reboot_host",
        "shutdown_host",
        "deploy_production",
        "execute_trade",
        "trade_crypto",
        "mint_nft",
    }

    def __init__(self):
        self.secret_key = settings.jarvis_secret_key.encode("utf-8")
        self.kill_switch_active = False
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        self.consumed_tokens: Set[str] = set()

    def trigger_kill_switch(self, reason: str = "Manual emergency stop") -> None:
        """Immediately halts all autonomous execution loops."""
        self.kill_switch_active = True

    def reset_kill_switch(self) -> None:
        self.kill_switch_active = False

    def is_kill_switch_active(self) -> bool:
        """Returns True if emergency kill switch is activated."""
        return self.kill_switch_active

    def hash_payload(self, payload: Any) -> str:
        """Generates canonical SHA-256 hash of task execution parameters."""
        data_str = str(payload).encode("utf-8")
        return hashlib.sha256(data_str).hexdigest()

    def generate_approval_token(
        self,
        task_id: str,
        power_id: str,
        payload_hash: str,
        user_id: Optional[str] = None,
    ) -> Tuple[str, float]:
        """Creates an HMAC-SHA256 token valid for the configured approval window bound to user_id."""
        effective_user_id = user_id or getattr(settings, "jarvis_user_id", "ganesh")
        expiry = int(time.time() + (settings.approval_token_expiry_minutes * 60))
        message = f"{effective_user_id}:{task_id}:{power_id}:{payload_hash}:{expiry}".encode("utf-8")
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        token = f"{signature}.{expiry}"
        return token, float(expiry)

    def request_approval(
        self,
        power_id: str,
        task_id: str,
        action_summary: str,
        payload: Any,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates an approval record and token bound to payload hash and user_id."""
        payload_hash = self.hash_payload(payload)
        effective_user_id = user_id or getattr(settings, "jarvis_user_id", "ganesh")
        token, expires_at = self.generate_approval_token(task_id, power_id, payload_hash, user_id=effective_user_id)
        approval_id = f"appr_{uuid.uuid4().hex[:12]}"
        record = {
            "id": approval_id,
            "approval_id": approval_id,
            "task_id": task_id,
            "power_id": power_id,
            "action_summary": action_summary,
            "payload_hash": payload_hash,
            "user_id": effective_user_id,
            "token": token,
            "expires_at": expires_at,
            "status": "PENDING",
        }
        self.pending_approvals[approval_id] = record
        self.pending_approvals[task_id] = record
        return record

    def verify_token(self, token: str) -> bool:
        """Verifies an HMAC approval token's signature and expiration."""
        try:
            sig, expiry_str = token.split(".")
            expiry = int(expiry_str)
            if time.time() > expiry:
                return False
            for appr in self.pending_approvals.values():
                if appr.get("token") == token or appr.get("id") == token or appr.get("approval_id") == token:
                    valid, _ = self.verify_approval_token(
                        appr["task_id"],
                        appr["power_id"],
                        appr["payload_hash"],
                        appr.get("token", token),
                        user_id=appr.get("user_id"),
                    )
                    return valid
            return False
        except Exception:
            return False

    def verify_state_approval(
        self,
        token: str,
        task_id: Optional[str] = None,
        power_id: Optional[str] = None,
        payload_hash: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Comprehensive cryptographic verification of an approval token or approval_id.
        1. Checks pending_approvals records by token, approval_id, or task_id.
           Enforces that pending approval records MUST have status == "APPROVED".
        2. If candidate parameters (task_id, power_id, payload_hash) are provided, verifies direct HMAC signature.
        Returns (is_valid, reason).
        """
        if not token or not isinstance(token, str):
            return False, "Approval token is missing or empty"

        # 1. Search pending_approvals records
        for appr in list(self.pending_approvals.values()):
            if appr.get("token") == token or appr.get("id") == token or appr.get("approval_id") == token:
                if power_id and appr.get("power_id") != power_id:
                    continue
                if task_id and appr.get("task_id") != task_id:
                    continue
                if payload_hash and appr.get("payload_hash") != payload_hash:
                    continue
                # Enforce that status must be APPROVED
                if appr.get("status") != "APPROVED":
                    return False, f"Approval request {token} has not been approved (status is {appr.get('status')})"
                return self.verify_approval_token(
                    task_id=appr.get("task_id", task_id or ""),
                    power_id=appr.get("power_id", power_id or ""),
                    payload_hash=appr.get("payload_hash", payload_hash or ""),
                    token=appr.get("token", token),
                    user_id=user_id or appr.get("user_id"),
                )

        # 2. Direct HMAC verification if task_id, power_id, and payload_hash are provided
        if task_id and power_id and payload_hash:
            return self.verify_approval_token(task_id, power_id, payload_hash, token, user_id=user_id)

        # 3. Direct verification of token format
        try:
            sig, expiry_str = token.split(".")
            expiry = int(expiry_str)
            if time.time() > expiry:
                return False, "Approval token has expired"
            if len(sig) != 64:
                return False, "Malformed approval token: invalid signature length"
        except Exception as exc:
            return False, f"Malformed approval token: {exc}"

        return False, "Approval token not recognized in pending approvals and missing cryptographic anchor"

    def consume_token(self, token: str) -> None:
        """Marks an approval token as consumed to prevent replay attacks."""
        self.consumed_tokens.add(token)

    def verify_approval_token(
        self,
        task_id: str,
        power_id: str,
        payload_hash: str,
        token: str,
        consume: bool = False,
        user_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Validates cryptographic HMAC signature, single-use validity, and expiration of an approval token.
        Supports dual-mode verification:
        1. 5-tuple: user_id:task_id:power_id:payload_hash:expiry
        2. Fallback legacy 4-tuple: task_id:power_id:payload_hash:expiry
        """
        try:
            if not token or not isinstance(token, str):
                return False, "Approval token is missing or empty"

            if token in self.consumed_tokens:
                return False, "Approval token has already been consumed"

            sig, expiry_str = token.split(".")
            expiry = int(expiry_str)
            if time.time() > expiry:
                return False, "Approval token has expired"

            effective_user_id = user_id or getattr(settings, "jarvis_user_id", "ganesh")

            # 1. Primary verification: 5-tuple HMAC bound to user_id
            msg_v2 = f"{effective_user_id}:{task_id}:{power_id}:{payload_hash}:{expiry}".encode("utf-8")
            expected_sig_v2 = hmac.new(self.secret_key, msg_v2, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected_sig_v2):
                if consume:
                    self.consume_token(token)
                return True, "Approval token valid and verified"

            # 2. Backward compatibility fallback: legacy 4-tuple HMAC
            msg_v1 = f"{task_id}:{power_id}:{payload_hash}:{expiry}".encode("utf-8")
            expected_sig_v1 = hmac.new(self.secret_key, msg_v1, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected_sig_v1):
                if consume:
                    self.consume_token(token)
                return True, "Approval token valid and verified (legacy format)"

            return False, "Invalid cryptographic signature on approval token"
        except Exception as e:
            return False, f"Malformed approval token: {str(e)}"

    def resolve_pending_approval(
        self,
        task_id: str,
        approved: bool,
        user_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Transitions a pending approval record. If approved, generates/returns the cryptographic approval token."""
        req = self.pending_approvals.get(task_id)
        if not req:
            return False, None

        effective_user_id = user_id or getattr(settings, "jarvis_user_id", "ganesh")

        if not approved:
            req["status"] = "REJECTED"
            self.pending_approvals.pop(task_id, None)
            return False, None

        token = req.get("token")
        if not token:
            token, expiry = self.generate_approval_token(
                task_id, req["power_id"], req["payload_hash"], user_id=effective_user_id
            )
            req["token"] = token
            req["expires_at"] = expiry

        req["status"] = "APPROVED"
        req["user_id"] = effective_user_id
        return True, token

    def evaluate_execution(
        self,
        task_id: str,
        power_id: str,
        privilege_level: int,
        payload: Dict[str, Any],
        approval_token: Optional[str] = None,
        user_id: Optional[str] = None,
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
        effective_user_id = user_id or getattr(settings, "jarvis_user_id", "ganesh")

        # 2. Level 0 & 1 (Reads) - Allow if configured
        if privilege_level <= 1:
            if not settings.allow_unapproved_reads and privilege_level == 1:
                return False, "Policy requires read approval in strict isolation mode", None
            return True, "Read operation cleared by Policy Gate", None

        # 3. Check if Power or Privilege Level requires approval
        needs_approval = (
            privilege_level >= 3
            or power_id.lower() in self.APPROVAL_REQUIRED_POWERS
            or any(danger_kw in power_id.lower() for danger_kw in ["delete", "drop", "deploy", "buy", "send", "kill"])
        )

        if needs_approval:
            if not approval_token:
                # Generate a pending approval request WITHOUT leaking token to client
                approval_id = f"appr_{uuid.uuid4().hex[:12]}"
                token, expiry = self.generate_approval_token(task_id, power_id, payload_hash, user_id=effective_user_id)
                # Internal server registry holds the generated token awaiting approval
                pending_record = {
                    "id": approval_id,
                    "approval_id": approval_id,
                    "task_id": task_id,
                    "power_id": power_id,
                    "payload_hash": payload_hash,
                    "user_id": effective_user_id,
                    "token": token,
                    "expires_at": expiry,
                    "status": "PENDING",
                    "action_summary": f"Execute {power_id} (Level {privilege_level} - {self.PRIVILEGE_LEVELS.get(privilege_level)})",
                }
                self.pending_approvals[task_id] = pending_record
                self.pending_approvals[approval_id] = pending_record

                # Returned approval_req for caller must NEVER contain the cryptographic secret token!
                client_approval_req = {
                    "approval_id": approval_id,
                    "task_id": task_id,
                    "power_id": power_id,
                    "payload_hash": payload_hash,
                    "user_id": effective_user_id,
                    "status": "PENDING",
                    "approval_required": True,
                    "expires_at": expiry,
                    "action_summary": pending_record["action_summary"],
                }
                return (
                    False,
                    f"POLICY REQUIREMENT: Human approval required for {power_id} (Level {privilege_level})",
                    client_approval_req,
                )

            # Single-use consumption check
            if approval_token in self.consumed_tokens:
                return False, "APPROVAL FAILED: Approval token has already been consumed", None

            # Verify token with single-use consumption and user binding
            valid, reason = self.verify_approval_token(
                task_id, power_id, payload_hash, approval_token, consume=True, user_id=effective_user_id
            )
            if not valid:
                return False, f"APPROVAL FAILED: {reason}", None

            # Mark pending record as consumed
            if task_id in self.pending_approvals:
                self.pending_approvals[task_id]["status"] = "CONSUMED"

        # 4. Allow-list Verifications
        # Directory check
        target_dir = payload.get("target_directory") or payload.get("directory") or payload.get("path")
        if target_dir:
            if not any(target_dir.startswith(allowed) for allowed in settings.allowed_directories):
                # If strict mode, deny
                if settings.policy_strict_mode and privilege_level >= 2:
                    return False, f"SECURITY VIOLATION: Path '{target_dir}' is not within allowed directories", None

        # Ensure token is recorded as consumed if an approval_token was provided
        if approval_token:
            self.consume_token(approval_token)
            if task_id in self.pending_approvals:
                self.pending_approvals[task_id]["status"] = "CONSUMED"

        return True, "Policy Gate approved execution", None


# Singleton Policy Gate
policy_gate = PolicyGate()
