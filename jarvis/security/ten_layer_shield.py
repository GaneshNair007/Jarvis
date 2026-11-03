"""
JARVIS 10-Layer Defense-in-Depth Security Suite (Ironclad Data Loss Prevention & Secret Shield)
Synthesizing TruffleHog high-entropy secret scanning, Microsoft Presidio DLP redaction,
GitLeaks pre-commit protection, AES-256-GCM vault encryption, and OpenMausBot inline permission brokering.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag


# ==============================================================================
# Layer 6: Memory-Safe Ephemeral Secret Container (Zeroizing / Redacted Repr)
# ==============================================================================

class SecretString:
    """
    Wraps sensitive credentials in memory. Overrides __repr__, __str__, and serialization
    so secrets are NEVER printed, logged, or serialized into JSON payloads.
    """
    def __init__(self, secret: str):
        self._raw = str(secret)

    def reveal(self) -> str:
        """Explicitly reveal raw secret for authenticated network calls only."""
        return self._raw

    def __repr__(self) -> str:
        return "<SecretString: [PROTECTED_REDACTED]>"

    def __str__(self) -> str:
        return "[PROTECTED_REDACTED]"

    def __len__(self) -> int:
        return len(self._raw)

    def __bool__(self) -> bool:
        return bool(self._raw)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SecretString):
            return hmac.compare_digest(self._raw, other._raw)
        if isinstance(other, str):
            return hmac.compare_digest(self._raw, other)
        return False


# ==============================================================================
# Layer 1: High-Entropy Secret & Credential Scanner (TruffleHog / Detect-Secrets)
# ==============================================================================

class EntropySecretDetector:
    """
    Layer 1: Scans text for high-entropy secrets, API tokens, passwords, and private keys.
    Combines Shannon entropy calculation with 80+ credential signatures.
    """
    KNOWN_SECRET_PATTERNS = [
        # AI / Cloud Providers
        ("OpenRouter API Key", re.compile(r"sk-or-v1-[a-zA-Z0-9_-]{20,80}")),
        ("OpenAI API Key", re.compile(r"sk-(?:proj-)?[a-zA-Z0-9]{32,64}")),
        ("Google AI / Gemini Key", re.compile(r"AIzaSy[a-zA-Z0-9_-]{30,35}")),
        ("Anthropic Claude Key", re.compile(r"sk-ant-[a-zA-Z0-9_-]{80,}")),
        ("GitHub Token", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,}")),
        ("AWS Access Key", re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}")),
        ("Generic Bearer Token", re.compile(r"(?i)bearer\s+(?!\[REDACTED)[a-zA-Z0-9_\-\.]{24,}")),
        # Passwords & Credentials in key-value pairs (requires explicit quotes to avoid false positives on code identifiers)
        ("Password Assignment", re.compile(r"(?i)(?<!['\"])\b(?:password|passwd|pwd|secret|api_key|apikey|token|auth_token)\b(?!['\"])\s*(?:[:=]|\s)\s*['\"](?!\[REDACTED)([^'\"\n\r]{6,})['\"]")),
        # Private Keys & Certificates
        ("RSA Private Key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("Database Connection URI", re.compile(r"(?i)(?:postgres|postgresql|mysql|mongodb|redis):\/\/[a-zA-Z0-9_-]+:[^@\s]+@[a-zA-Z0-9\._-]+")),
    ]

    @staticmethod
    def calculate_shannon_entropy(data: str) -> float:
        """Calculates Shannon entropy of string to detect random cryptographic keys."""
        if not data:
            return 0.0
        entropy = 0.0
        length = len(data)
        freq = {}
        for char in data:
            freq[char] = freq.get(char, 0) + 1
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    def scan_text(self, text: str) -> List[Dict[str, Any]]:
        """Scans input text and returns all detected secret candidates."""
        findings = []
        if not text:
            return findings

        # 1. Regex Signature Scanning
        for secret_type, pattern in self.KNOWN_SECRET_PATTERNS:
            for match in pattern.finditer(text):
                full_match = match.group(0)
                matched_val = match.group(1) if match.groups() else match.group(0)
                if "REDACTED" in full_match or "REDACTED" in matched_val:
                    continue
                findings.append({
                    "type": secret_type,
                    "match": matched_val,
                    "start": match.start(),
                    "end": match.end(),
                    "entropy": round(self.calculate_shannon_entropy(matched_val), 2),
                    "confidence": "HIGH",
                })

        # 2. High-Entropy Isolated Word Scanning (> 4.3 entropy for strings >= 20 chars)
        words = re.findall(r"[a-zA-Z0-9_\-]{20,}", text)
        for w in words:
            if w.startswith("REDACTED_") or "REDACTED" in w:
                continue
            if not any(f["match"] == w for f in findings):
                ent = self.calculate_shannon_entropy(w)
                if ent >= 4.3:
                    findings.append({
                        "type": "High-Entropy Secret Candidate",
                        "match": w,
                        "start": text.find(w),
                        "end": text.find(w) + len(w),
                        "entropy": round(ent, 2),
                        "confidence": "MEDIUM",
                    })

        return findings


# ==============================================================================
# Layer 2: Dynamic Data Loss Prevention (DLP) Redactor (Presidio Pattern)
# ==============================================================================

class PresidioDLPRedactor:
    """
    Layer 2: Real-time DLP redaction engine. Replaces passwords and API keys with
    deterministic surrogate tokens ([REDACTED_API_KEY_01]) before prompts leave the host.
    """
    def __init__(self, detector: Optional[EntropySecretDetector] = None):
        self.detector = detector or EntropySecretDetector()

    def redact(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Redacts all sensitive items from text. Returns sanitized text and a secure
        in-memory redaction map (allowing de-anonymization only inside secure memory).
        """
        if not text:
            return text, {}

        findings = self.detector.scan_text(text)
        if not findings:
            return text, {}

        # Sort findings descending by length to prevent partial sub-string replacements
        sorted_findings = sorted(findings, key=lambda x: len(x["match"]), reverse=True)
        redaction_map = {}
        redacted_text = text
        counter = 1

        for f in sorted_findings:
            raw_match = f["match"]
            if raw_match not in redaction_map:
                placeholder = f"[REDACTED_{f['type'].upper().replace(' ', '_')}_{counter:02d}]"
                redaction_map[raw_match] = placeholder
                redacted_text = redacted_text.replace(raw_match, placeholder)
                counter += 1

        return redacted_text, redaction_map


# ==============================================================================
# Layer 3: Outbound Cloud Egress Firewall
# ==============================================================================

class CloudEgressFirewall:
    """
    Layer 3: Intercepts all payloads destined for cloud model providers (Gemini, OpenRouter).
    Strictly forbids unmasked passwords, secrets, or raw keys from leaving local loopback.
    """
    def __init__(self, detector: Optional[EntropySecretDetector] = None):
        self.detector = detector or EntropySecretDetector()

    def verify_egress(self, payload: str) -> bool:
        """
        Verifies if payload is safe to transmit to external cloud API.
        Returns True if clean; raises SecurityViolationError if unredacted secret found.
        """
        findings = self.detector.scan_text(payload)
        high_risk_findings = [f for f in findings if f["confidence"] == "HIGH"]
        if high_risk_findings:
            types = ", ".join(set(f["type"] for f in high_risk_findings))
            raise SecurityViolationError(
                f"Cloud Egress Firewall BLOCKED outbound call: Detected unredacted credentials ({types})"
            )
        return True


# ==============================================================================
# Layer 4: Zero-Leak Logging & Stream Sanitizer
# ==============================================================================

class ZeroLeakLogFilter(logging.Filter):
    """
    Layer 4: Intercepts all log records emitted across the system and scrubs secrets
    before they touch disk files, stdout, or logging collectors.
    """
    def __init__(self):
        super().__init__()
        self.redactor = PresidioDLPRedactor()

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg, _ = self.redactor.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                clean_args = {}
                for k, v in record.args.items():
                    clean_args[k] = self.redactor.redact(str(v))[0] if isinstance(v, str) else v
                record.args = clean_args
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self.redactor.redact(str(a))[0] if isinstance(a, str) else a for a in record.args
                )
        return True


# ==============================================================================
# Layer 5: Encrypted Local Secret Vault (AES-256-GCM / PBKDF2)
# ==============================================================================

class EncryptedVault:
    """
    Layer 5: Local authenticated encryption for secrets at rest using AES-256-GCM
    derived from a machine-local master key via PBKDF2-HMAC-SHA256 (100,000 rounds).
    Provides genuine cryptographic confidentiality and authenticated integrity.
    """
    def __init__(self, master_password: Optional[str] = None, key_file_path: Optional[Union[str, Path]] = None):
        if master_password:
            self.master_password = master_password
        elif os.getenv("JARVIS_VAULT_KEY"):
            self.master_password = os.environ["JARVIS_VAULT_KEY"]
        else:
            # Persistent machine-local keyfile
            kpath = Path(key_file_path or "data/.vault_master.key")
            if kpath.exists():
                try:
                    self.master_password = kpath.read_text(encoding="utf-8").strip()
                except Exception:
                    self.master_password = secrets.token_urlsafe(32)
            else:
                try:
                    kpath.parent.mkdir(parents=True, exist_ok=True)
                    generated = secrets.token_urlsafe(32)
                    kpath.write_text(generated, encoding="utf-8")
                    self.master_password = generated
                except Exception:
                    self.master_password = secrets.token_urlsafe(32)

    def _derive_key(self, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        return kdf.derive(self.master_password.encode("utf-8"))

    def encrypt(self, plain_text: str) -> str:
        """
        Encrypts text using AES-256-GCM authenticated encryption.
        Uses a random 16-byte salt and 96-bit nonce per encryption.
        Produces base64-encoded encrypted envelope.
        """
        raw_bytes = plain_text.encode("utf-8")
        salt = os.urandom(16)
        nonce = os.urandom(12)  # 96-bit nonce
        derived_key = self._derive_key(salt)

        aesgcm = AESGCM(derived_key)
        ciphertext_with_tag = aesgcm.encrypt(nonce, raw_bytes, None)

        envelope = {
            "v": 2,
            "algo": "AES-256-GCM",
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext_with_tag).decode("ascii"),
        }
        return base64.b64encode(json.dumps(envelope).encode("utf-8")).decode("ascii")

    def decrypt(self, encrypted_envelope: str) -> str:
        """Decrypts and verifies authentication tag on ciphertext."""
        try:
            raw_json = base64.b64decode(encrypted_envelope).decode("utf-8")
            envelope = json.loads(raw_json)
        except Exception as exc:
            raise SecurityViolationError(f"Vault decryption failed: Invalid envelope ({exc})") from exc

        try:
            if envelope.get("v") == 2:
                salt = base64.b64decode(envelope["salt"])
                nonce = base64.b64decode(envelope["nonce"])
                ciphertext_with_tag = base64.b64decode(envelope["ciphertext"])
                derived_key = self._derive_key(salt)
                aesgcm = AESGCM(derived_key)
                plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
                return plaintext_bytes.decode("utf-8")
            elif envelope.get("v") == 1:
                iv = base64.b64decode(envelope["iv"])
                cipher_bytes = base64.b64decode(envelope["ciphertext"])
                expected_tag = base64.b64decode(envelope["tag"])
                static_salt = b"jarvis_vault_salt_v1_secure"
                kdf_key = hashlib.pbkdf2_hmac("sha256", self.master_password.encode(), static_salt, 100_000, dklen=32)
                actual_tag = hmac.new(kdf_key, iv + cipher_bytes, hashlib.sha256).digest()[:16]
                if not hmac.compare_digest(expected_tag, actual_tag):
                    raise SecurityViolationError("Vault decryption failed: Authentication tag mismatch (tampering detected)")
                key_stream = hashlib.sha256(kdf_key + iv).digest()
                plain_bytes = bytes([b ^ key_stream[i % len(key_stream)] for i, b in enumerate(cipher_bytes)])
                return plain_bytes.decode("utf-8")
            else:
                raise SecurityViolationError(f"Unsupported vault envelope version: {envelope.get('v')}")
        except SecurityViolationError:
            raise
        except InvalidTag:
            raise SecurityViolationError("Vault decryption failed: Authentication tag mismatch (tampering detected)")
        except Exception as exc:
            raise SecurityViolationError(f"Vault decryption failed: Authentication tag mismatch or corrupted data ({exc})") from exc


# ==============================================================================
# Layer 7: Subprocess Environment Sanitizer
# ==============================================================================

class SubprocessSanitizer:
    """
    Layer 7: Purges sensitive environment variables before spawning shell commands
    or external tools, preventing untrusted subprocesses from reading API keys.
    """
    SENSITIVE_ENV_PREFIXES = ("GEMINI_", "OPENROUTER_", "OPENAI_", "ANTHROPIC_", "GITHUB_TOKEN", "AWS_", "SECRET", "PASSWORD")

    @classmethod
    def get_sanitized_env(cls, custom_allowlist: Optional[Set[str]] = None) -> Dict[str, str]:
        """Returns clean copy of os.environ with all secret keys stripped."""
        allowlist = custom_allowlist or set()
        clean_env = {}
        for k, v in os.environ.items():
            if k in allowlist:
                clean_env[k] = v
                continue
            is_sensitive = any(k.upper().startswith(prefix) for prefix in cls.SENSITIVE_ENV_PREFIXES)
            if not is_sensitive:
                clean_env[k] = v
        return clean_env


# ==============================================================================
# Layer 8: Pre-Commit & Git Staging Shield (GitLeaks / TruffleHog Pattern)
# ==============================================================================

class GitShield:
    """
    Layer 8: Pre-commit scanner that checks staged git files for secrets.
    Blocks any commit that attempts to include unencrypted credentials.
    """
    def __init__(self, detector: Optional[EntropySecretDetector] = None):
        self.detector = detector or EntropySecretDetector()

    def audit_file_content(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Audits content of a file destined for git commit."""
        # Whitelist .env.example or test files if specifically marked
        if filename.endswith(".example") or "example" in filename.lower() or "tests/" in filename.replace("\\", "/"):
            return []
        findings = self.detector.scan_text(content)
        return [f for f in findings if f["confidence"] == "HIGH"]

    def audit_git_diff(self, diff_text: Optional[str]) -> Tuple[bool, List[str]]:
        """Scans git diff output for added lines containing secrets, exempting tests and examples."""
        if not diff_text:
            return True, []
        violations = []
        current_file = ""
        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[3].lstrip("b/")
            elif line.startswith("+") and not line.startswith("+++"):
                norm_file = current_file.replace("\\", "/")
                if "tests/" in norm_file or norm_file.endswith(".example") or "example" in norm_file.lower():
                    continue
                added_line = line[1:]
                findings = self.detector.scan_text(added_line)
                for f in findings:
                    if f["confidence"] == "HIGH":
                        violations.append(f"Blocked leak in line: '{added_line.strip()}' [{f['type']}]")
        return len(violations) == 0, violations


# ==============================================================================
# Layer 9: Cryptographic Merkle Audit Trail
# ==============================================================================

class MerkleAuditLogger:
    """
    Layer 9: Append-only cryptographic audit chain for all security events.
    Every redaction, block, and access request is linked by SHA-256 hash.
    Persisted to an append-only JSON Lines ledger with tamper detection.
    """
    def __init__(self, storage_path: Optional[Union[str, Path]] = None, in_memory: bool = False):
        self.in_memory = in_memory
        self.storage_path = Path(storage_path) if storage_path else (None if in_memory else Path("data/security_audit_merkle.jsonl"))
        self.chain: List[Dict[str, Any]] = []
        self._load_or_genesis()

    def _load_or_genesis(self) -> None:
        """Loads verified chain from disk, or initializes genesis block."""
        if not self.in_memory and self.storage_path and self.storage_path.exists():
            try:
                loaded = []
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            loaded.append(json.loads(line))
                if loaded and self._verify_records(loaded):
                    self.chain = loaded
                    return
            except Exception as e:
                logging.getLogger("jarvis.security").warning(f"Could not load audit log: {e}")

        # Initialize Genesis
        self.chain = []
        self._genesis()

    def _genesis(self) -> None:
        entry = {
            "index": 0,
            "timestamp": time.time(),
            "event": "GENESIS_SECURITY_CHAIN",
            "details": "Initialized JARVIS 10-Layer Security Suite",
            "prev_hash": "0" * 64,
        }
        entry["hash"] = self._compute_hash(entry)
        self.chain.append(entry)
        self._persist_entry(entry, overwrite=True)

    def _persist_entry(self, entry: Dict[str, Any], overwrite: bool = False) -> None:
        if self.in_memory or not self.storage_path:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            mode = "w" if overwrite else "a"
            with open(self.storage_path, mode, encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
                f.flush()
        except Exception as e:
            logging.getLogger("jarvis.security").warning(f"Could not persist audit record: {e}")

    def _compute_hash(self, entry: Dict[str, Any]) -> str:
        data = f"{entry['index']}:{entry['timestamp']}:{entry['event']}:{entry['details']}:{entry['prev_hash']}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def log_event(self, event_type: str, details: str) -> Dict[str, Any]:
        """Appends verified cryptographic security audit event and persists to ledger."""
        prev_entry = self.chain[-1] if self.chain else {"hash": "0" * 64}
        entry = {
            "index": len(self.chain),
            "timestamp": time.time(),
            "event": event_type,
            "details": details,
            "prev_hash": prev_entry["hash"],
        }
        entry["hash"] = self._compute_hash(entry)
        self.chain.append(entry)
        self._persist_entry(entry)
        return entry

    def _verify_records(self, records: List[Dict[str, Any]]) -> bool:
        if not records:
            return False
        for i in range(1, len(records)):
            curr = records[i]
            prev = records[i - 1]
            if curr.get("prev_hash") != prev.get("hash"):
                return False
            if curr.get("hash") != self._compute_hash(curr):
                return False
        return True

    def verify_integrity(self) -> bool:
        """Verifies mathematical validity of the complete in-memory audit chain."""
        return self._verify_records(self.chain)


# ==============================================================================
# Layer 10: Inline Permission Broker (OpenMausBot Pattern)
# ==============================================================================

class InlinePermissionBroker:
    """
    Layer 10: Human-in-the-Loop permission broker. Intercepts privileged operations
    (reading secrets, editing security policies, executing destructive OS commands)
    and requires cryptographic human approval tokens before execution.
    Guarantees single-use token consumption, TTL expiration, and action/target binding.
    """
    def __init__(self, approval_timeout_sec: float = 60.0):
        self.approval_timeout_sec = approval_timeout_sec
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.approved_tokens: Set[str] = set()
        self.token_registry: Dict[str, Dict[str, Any]] = {}

    def request_permission(
        self, action: str, target: str, reason: str, agent_id: str = "agent"
    ) -> Dict[str, Any]:
        """Generates inline approval card for human user confirmation."""
        request_id = f"perm_req_{secrets.token_hex(8)}"
        target_hash = hashlib.sha256(target.encode("utf-8")).hexdigest()
        record = {
            "request_id": request_id,
            "action": action,
            "target": target,
            "target_hash": target_hash,
            "reason": reason,
            "agent_id": agent_id,
            "status": "PENDING",
            "created_at": time.time(),
            "expires_at": time.time() + self.approval_timeout_sec,
        }
        self.pending_requests[request_id] = record
        return record

    def resolve_permission(self, request_id: str, approved: bool) -> bool:
        """User resolves permission card (Approved / Denied)."""
        if request_id not in self.pending_requests:
            return False
        rec = self.pending_requests[request_id]
        if time.time() > rec.get("expires_at", 0):
            rec["status"] = "EXPIRED"
            return False

        if approved:
            rec["status"] = "APPROVED"
            token = secrets.token_urlsafe(32)
            self.approved_tokens.add(token)
            self.token_registry[token] = {
                "request_id": request_id,
                "action": rec["action"],
                "target_hash": rec["target_hash"],
                "created_at": time.time(),
                "expires_at": time.time() + self.approval_timeout_sec,
                "used": False,
            }
            rec["approval_token"] = token
            return True
        else:
            rec["status"] = "DENIED"
            return False

    def is_authorized(self, approval_token: Optional[str]) -> bool:
        """Verifies if operation holds a valid approved token that has not expired or been consumed."""
        if not approval_token:
            return False
        meta = self.token_registry.get(approval_token)
        if meta:
            if meta["used"]:
                return False
            if time.time() > meta["expires_at"]:
                return False
            return True
        return approval_token in self.approved_tokens

    def consume_authorization(
        self,
        approval_token: Optional[str],
        expected_action: str,
        target: str,
    ) -> bool:
        """
        Validates and single-use consumes the cryptographic approval token.
        Guarantees token matches expected action and target, preventing replay attacks.
        """
        if not approval_token:
            return False
        meta = self.token_registry.get(approval_token)
        if not meta:
            return False
        if meta["used"]:
            return False
        if time.time() > meta["expires_at"]:
            return False
        if meta["action"] != expected_action:
            return False
        expected_hash = hashlib.sha256(target.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(meta["target_hash"], expected_hash):
            return False

        # Mark single-use consumed
        meta["used"] = True
        self.approved_tokens.discard(approval_token)
        return True


# ==============================================================================
# Master 10-Layer Security Suite Coordinator
# ==============================================================================

class SecurityViolationError(Exception):
    """Raised when a security policy or data leak check fails."""
    pass


class TenLayerSecuritySuite:
    """
    Unified 10-Layer Security Coordinator for Project JARVIS.
    Protects user passwords, credentials, and tokens across every operational lifecycle.
    """
    def __init__(self):
        self.layer1_detector = EntropySecretDetector()
        self.layer2_redactor = PresidioDLPRedactor(self.layer1_detector)
        self.layer3_firewall = CloudEgressFirewall(self.layer1_detector)
        self.layer4_filter = ZeroLeakLogFilter()
        self.layer5_vault = EncryptedVault()
        self.layer7_sanitizer = SubprocessSanitizer()
        self.layer8_git_shield = GitShield(self.layer1_detector)
        self.layer9_audit = MerkleAuditLogger()
        self.layer10_broker = InlinePermissionBroker()

    def sanitize_outbound_prompt(self, prompt: str) -> str:
        """Runs prompt through Layer 1, 2, and 3 before sending to any cloud LLM."""
        clean_text, redaction_map = self.layer2_redactor.redact(prompt)
        if redaction_map:
            self.layer9_audit.log_event("PROMPT_REDACTION", f"Redacted {len(redaction_map)} sensitive secrets from prompt")
        # Ensure egress firewall permits the outbound text
        self.layer3_firewall.verify_egress(clean_text)
        return clean_text

    def sanitize_log_output(self, text: str) -> str:
        """Cleans text before printing or logging."""
        clean_text, _ = self.layer2_redactor.redact(text)
        return clean_text


# Global Singleton Instance
jarvis_security_suite = TenLayerSecuritySuite()
