"""
Comprehensive Empirical Verification Suite for the JARVIS 10-Layer Security Suite
Tests all 10 layers of defense-in-depth security, ensuring zero password or API key leakage.
"""

import logging
import pytest
from jarvis.security.ten_layer_shield import (
    EntropySecretDetector,
    PresidioDLPRedactor,
    CloudEgressFirewall,
    ZeroLeakLogFilter,
    EncryptedVault,
    SecretString,
    SubprocessSanitizer,
    GitShield,
    MerkleAuditLogger,
    InlinePermissionBroker,
    TenLayerSecuritySuite,
    SecurityViolationError,
    jarvis_security_suite,
)


class TestTenLayerSecuritySuite:

    # ── Layer 1: High-Entropy Secret & Key Scanner ─────────────────────────────
    def test_layer1_detects_api_keys_and_passwords(self):
        detector = EntropySecretDetector()
        sample = (
            "Here is my config: openrouter=sk-or-v1-DUMMY_TEST_KEY_NOT_REAL_SAMPLE_1234567890\n"
            "password = 'SuperSecretMasterPassword123!' and gemini = AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6\n"
        )
        findings = detector.scan_text(sample)
        assert len(findings) >= 3
        types = [f["type"] for f in findings]
        assert "OpenRouter API Key" in types
        assert "Google AI / Gemini Key" in types
        assert any("Password" in t for t in types)

    # ── Layer 2: Dynamic DLP Redactor (Presidio) ──────────────────────────────
    def test_layer2_redacts_credentials_cleanly(self):
        redactor = PresidioDLPRedactor()
        raw = "Connect with token sk-or-v1-DUMMY_TEST_KEY_NOT_REAL_SAMPLE_1234567890 and password 'MySecretPass123!'"
        cleaned, rmap = redactor.redact(raw)
        assert "sk-or-v1" not in cleaned
        assert "MySecretPass123!" not in cleaned
        assert "[REDACTED_" in cleaned
        assert len(rmap) >= 2

    # ── Layer 3: Cloud Egress Firewall ────────────────────────────────────────
    def test_layer3_blocks_unredacted_egress(self):
        firewall = CloudEgressFirewall()
        dangerous_payload = "Send this prompt to cloud: API key is sk-or-v1-DUMMY_TEST_KEY_NOT_REAL_SAMPLE_1234567890"
        with pytest.raises(SecurityViolationError) as exc_info:
            firewall.verify_egress(dangerous_payload)
        assert "BLOCKED outbound call" in str(exc_info.value)

        # Redacted payload is permitted
        clean_payload = "Send this prompt to cloud: API key is [REDACTED_OPENROUTER_API_KEY_01]"
        assert firewall.verify_egress(clean_payload) is True

    # ── Layer 4: Zero-Leak Log Sanitizer ──────────────────────────────────────
    def test_layer4_log_filter_scrubs_records(self):
        log_filter = ZeroLeakLogFilter()
        record = logging.LogRecord(
            name="jarvis_test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="User entered password = 'SuperSecretPassword999!' for login",
            args=(),
            exc_info=None,
        )
        log_filter.filter(record)
        assert "SuperSecretPassword999!" not in record.msg
        assert "[REDACTED_" in record.msg

    # ── Layer 5: Encrypted Local Vault (AES-256-GCM / PBKDF2) ─────────────────
    def test_layer5_encrypted_vault_encrypt_decrypt_and_tamper_detection(self):
        vault = EncryptedVault(master_password="test-secure-master-password")
        secret = "ultra-sensitive-master-vault-credential"
        encrypted = vault.encrypt(secret)
        assert encrypted != secret
        assert secret not in encrypted

        # Decrypts correctly
        decrypted = vault.decrypt(encrypted)
        assert decrypted == secret

        # Tampering is detected
        tampered = encrypted[:-4] + "AAAA"
        with pytest.raises(SecurityViolationError):
            vault.decrypt(tampered)

    # ── Layer 6: Ephemeral SecretString ───────────────────────────────────────
    def test_layer6_secret_string_masks_repr_and_str(self):
        secret = SecretString("my-raw-secret-key-12345")
        assert repr(secret) == "<SecretString: [PROTECTED_REDACTED]>"
        assert str(secret) == "[PROTECTED_REDACTED]"
        assert "my-raw-secret-key-12345" not in str(secret)
        assert secret.reveal() == "my-raw-secret-key-12345"
        assert secret == "my-raw-secret-key-12345"

    # ── Layer 7: Subprocess Environment Sanitizer ─────────────────────────────
    def test_layer7_subprocess_env_sanitizer(self, monkeypatch):
        monkeypatch.setenv("GEMINI_KEY_ACCOUNT_1", "secret_gemini_val")
        monkeypatch.setenv("OPENROUTER_API_KEY", "secret_openrouter_val")
        monkeypatch.setenv("PATH", "C:\\Windows\\System32")

        clean_env = SubprocessSanitizer.get_sanitized_env()
        assert "PATH" in clean_env
        assert "GEMINI_KEY_ACCOUNT_1" not in clean_env
        assert "OPENROUTER_API_KEY" not in clean_env

    # ── Layer 8: Pre-Commit Git Shield ────────────────────────────────────────
    def test_layer8_git_shield_detects_leaks_in_diff(self):
        git_shield = GitShield()
        diff = (
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "+OPENROUTER_KEY = 'sk-or-v1-DUMMY_TEST_KEY_NOT_REAL_SAMPLE_1234567890'\n"
            "+print('initialized')\n"
        )
        passed, violations = git_shield.audit_git_diff(diff)
        assert passed is False
        assert len(violations) > 0
        assert "Blocked leak in line" in violations[0]

    # ── Layer 9: Merkle Audit Trail ───────────────────────────────────────────
    def test_layer9_merkle_audit_integrity(self):
        audit = MerkleAuditLogger()
        audit.log_event("POLICY_BLOCK", "Blocked access to /etc/shadow")
        audit.log_event("SECRET_REDACT", "Redacted OpenAI key from user turn")
        assert len(audit.chain) == 3  # Genesis + 2 events
        assert audit.verify_integrity() is True

        # Tampering breaks hash integrity
        audit.chain[1]["details"] = "Tampered details"
        assert audit.verify_integrity() is False

    # ── Layer 10: Inline Permission Broker ────────────────────────────────────
    def test_layer10_inline_permission_broker(self):
        broker = InlinePermissionBroker()
        req = broker.request_permission("ACCESS_CREDENTIALS", "Vault", "User requested DB export")
        req_id = req["request_id"]
        assert broker.is_authorized(None) is False

        # Deny
        broker.resolve_permission(req_id, approved=False)
        assert broker.pending_requests[req_id]["status"] == "DENIED"

        # Request new and approve
        req2 = broker.request_permission("ACCESS_CREDENTIALS", "Vault", "Approved export")
        req2_id = req2["request_id"]
        broker.resolve_permission(req2_id, approved=True)
        token = broker.pending_requests[req2_id]["approval_token"]
        assert broker.is_authorized(token) is True

    # ── Master Suite Coordinator ──────────────────────────────────────────────
    def test_master_suite_sanitize_outbound_prompt(self):
        suite = TenLayerSecuritySuite()
        prompt = "Hello Jarvis, here is my password = 'SecretPassword42' and key sk-or-v1-DUMMY_TEST_KEY_NOT_REAL_SAMPLE_1234567890"
        clean_prompt = suite.sanitize_outbound_prompt(prompt)
        assert "SecretPassword42" not in clean_prompt
        assert "sk-or-v1" not in clean_prompt
        assert "[REDACTED_" in clean_prompt
        assert suite.layer9_audit.verify_integrity() is True
