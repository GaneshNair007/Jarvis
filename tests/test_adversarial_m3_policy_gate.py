"""
Empirical Adversarial Test Suite for PolicyGate & Authorization Defenses (Milestone M3)
Author: Challenger M3-1 (teamwork_challenger)

This suite rigorously challenges:
1. Token extraction from refusal payloads (direct keys, recursive inspection, approval_id reuse, status manipulation)
2. Single and concurrent token replay (sequential replay, 50-thread concurrent race conditions, cross-power replay)
3. Cross-user token substitution (Alice/Bob substitution, user impersonation, default fallback isolation, colon injection)
4. Cryptographic signature and timestamp forgery (truncated HMAC, bit flips, future timestamp extension, expired tokens,
   malformed formats, type confusion, null bytes)
5. Fail-closed invariants (kill switch overrides valid tokens, unapproved reads, pending state hijacking)
"""

import hmac
import hashlib
import time
import uuid
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from jarvis.config import settings
from jarvis.core.policy_gate import PolicyGate, policy_gate
from jarvis.api.server import app

client = TestClient(app)


# ==============================================================================
# 1. TOKEN EXTRACTION FROM REFUSAL PAYLOADS
# ==============================================================================


class TestTokenExtractionAttacks:
    """Attempts to discover, extract, or reconstruct execution tokens from refusal payloads."""

    def test_refusal_payload_strictly_omits_tokens_and_secrets(self):
        """Verify that evaluate_execution refusal payload does not contain token or secret fields."""
        gate = PolicyGate()
        task_id = f"tsk_extract_{uuid.uuid4().hex[:8]}"
        payload = {"action": "drop_production_db", "cascade": True}

        allowed, reason, refusal_dict = gate.evaluate_execution(
            task_id=task_id,
            power_id="drop_database",
            privilege_level=5,
            payload=payload,
        )

        assert allowed is False
        assert "Human approval required" in reason
        assert isinstance(refusal_dict, dict)

        # 1. Blacklisted key check
        forbidden_keys = {
            "token",
            "approval_token",
            "secret",
            "secret_key",
            "sig",
            "signature",
            "hmac",
            "key",
            "auth_token",
        }
        for k in refusal_dict.keys():
            assert k.lower() not in forbidden_keys, f"Forbidden key '{k}' exposed in refusal payload!"

        # 2. Value inspection: check that no value contains a 64-character hex HMAC signature or token pattern
        token_pattern = re.compile(r"^[a-f0-9]{64}\.\d+$")
        hmac_pattern = re.compile(r"[a-f0-9]{64}")

        for k, v in refusal_dict.items():
            str_val = str(v)
            assert not token_pattern.match(str_val), f"Field '{k}' contains a valid token format: {str_val}"
            # Check for embedded raw 64-char hex strings (except payload_hash which is SHA-256 of payload)
            if k != "payload_hash":
                assert not hmac_pattern.search(str_val), f"Field '{k}' contains an HMAC or SHA string: {str_val}"

        # 3. Status must strictly be PENDING
        assert refusal_dict.get("status") == "PENDING"
        assert refusal_dict.get("approval_required") is True
        assert "approval_id" in refusal_dict
        assert refusal_dict["approval_id"].startswith("appr_")

    def test_approval_id_cannot_be_reused_as_execution_token(self):
        """Attempt to bypass execution authorization by submitting approval_id as approval_token."""
        gate = PolicyGate()
        task_id = f"tsk_appr_reuse_{uuid.uuid4().hex[:8]}"
        payload = {"disk": "/dev/nvme0n1", "wipe": True}

        # Step 1: Initial request creates pending approval
        _, _, refusal = gate.evaluate_execution(
            task_id=task_id, power_id="format_disk", privilege_level=5, payload=payload
        )
        approval_id = refusal["approval_id"]

        # Step 2: Adversary tries passing approval_id as approval_token
        allowed, reason, _ = gate.evaluate_execution(
            task_id=task_id,
            power_id="format_disk",
            privilege_level=5,
            payload=payload,
            approval_token=approval_id,
        )
        assert allowed is False
        assert "APPROVAL FAILED" in reason
        assert "Malformed approval token" in reason

    def test_approval_id_appended_with_timestamp_fails_cryptographic_verification(self):
        """Attempt to synthesize a valid token format f'{approval_id}.{expiry}'."""
        gate = PolicyGate()
        task_id = f"tsk_synth_{uuid.uuid4().hex[:8]}"
        payload = {"path": "/etc/shadow"}

        _, _, refusal = gate.evaluate_execution(
            task_id=task_id, power_id="delete_file", privilege_level=5, payload=payload
        )
        approval_id = refusal["approval_id"]
        expiry = refusal["expires_at"]

        # Synthetic token with approval_id as signature
        synthetic_token = f"{approval_id}.{int(expiry)}"
        allowed, reason, _ = gate.evaluate_execution(
            task_id=task_id,
            power_id="delete_file",
            privilege_level=5,
            payload=payload,
            approval_token=synthetic_token,
        )
        assert allowed is False
        assert "Invalid cryptographic signature" in reason or "Malformed" in reason

    def test_verify_state_approval_rejects_pending_and_rejected_statuses(self):
        """Directly query verify_state_approval while approval record is PENDING or REJECTED."""
        gate = PolicyGate()
        task_id = f"tsk_status_test_{uuid.uuid4().hex[:8]}"
        payload = {"to": "victim@example.com", "body": "phish"}
        payload_hash = gate.hash_payload(payload)

        # 1. Generate pending approval
        record = gate.request_approval("send_email", task_id, "Send email", payload)
        approval_id = record["approval_id"]
        raw_token = record["token"]

        # State is PENDING -> verify_state_approval must fail
        valid, msg = gate.verify_state_approval(
            token=approval_id, task_id=task_id, power_id="send_email", payload_hash=payload_hash
        )
        assert valid is False
        assert "has not been approved" in msg
        assert "PENDING" in msg

        # 2. Reject the approval
        gate.resolve_pending_approval(task_id, approved=False)
        valid_rejected, msg_rejected = gate.verify_state_approval(
            token=approval_id, task_id=task_id, power_id="send_email", payload_hash=payload_hash
        )
        assert valid_rejected is False
        assert ("has not been approved" in msg_rejected or "not recognized" in msg_rejected)

    def test_client_refusal_dictionary_mutation_does_not_poison_gate_state(self):
        """Verify that tampering with the returned client refusal dictionary does not modify internal gate records."""
        gate = PolicyGate()
        task_id = f"tsk_mutate_{uuid.uuid4().hex[:8]}"
        payload = {"command": "reboot"}

        _, _, refusal = gate.evaluate_execution(
            task_id=task_id, power_id="reboot_host", privilege_level=5, payload=payload
        )

        # Attacker modifies the client refusal dictionary in-place
        refusal["status"] = "APPROVED"
        refusal["token"] = "fake_token_injected"

        # Internal state in pending_approvals must remain pristine
        internal_record = gate.pending_approvals[task_id]
        assert internal_record["status"] == "PENDING"
        assert internal_record["token"] != "fake_token_injected"
        assert internal_record["token"].endswith(f".{int(internal_record['expires_at'])}")


# ==============================================================================
# 2. SINGLE AND CONCURRENT TOKEN REPLAY ATTACKS
# ==============================================================================


class TestTokenReplayAttacks:
    """Stress tests single-use token consumption under sequential and concurrent replay conditions."""

    def test_sequential_token_replay_rejected(self):
        """A valid approval token executed once must be rejected on every subsequent attempt."""
        gate = PolicyGate()
        task_id = f"tsk_seq_{uuid.uuid4().hex[:8]}"
        power_id = "wipe_system"
        payload = {"target": "/dev/sda"}
        payload_hash = gate.hash_payload(payload)

        token, _ = gate.generate_approval_token(task_id, power_id, payload_hash)

        # 1. First execution: succeeds and consumes token
        allowed1, msg1, _ = gate.evaluate_execution(
            task_id=task_id, power_id=power_id, privilege_level=5, payload=payload, approval_token=token
        )
        assert allowed1 is True
        assert "approved execution" in msg1.lower()
        assert token in gate.consumed_tokens

        # 2. Second execution (replay): MUST fail closed
        allowed2, msg2, _ = gate.evaluate_execution(
            task_id=task_id, power_id=power_id, privilege_level=5, payload=payload, approval_token=token
        )
        assert allowed2 is False
        assert "already been consumed" in msg2.lower()

        # 3. Third execution (replay with different task_id): MUST fail closed
        allowed3, msg3, _ = gate.evaluate_execution(
            task_id="tsk_other", power_id=power_id, privilege_level=5, payload=payload, approval_token=token
        )
        assert allowed3 is False
        assert "already been consumed" in msg3.lower()

    def test_massive_concurrent_token_replay_race_condition(self):
        """
        Adversarial Race Condition: 50 concurrent worker threads attempt simultaneous replay of a single token.
        Invariant: Exactly 1 invocation MUST succeed; exactly 49 invocations MUST fail closed.
        """
        gate = PolicyGate()
        task_id = f"tsk_race_50_{uuid.uuid4().hex[:8]}"
        power_id = "deploy_production"
        payload = {"commit_sha": "a1b2c3d4e5f6"}
        payload_hash = gate.hash_payload(payload)

        token, _ = gate.generate_approval_token(task_id, power_id, payload_hash)

        results = []

        def worker(thread_idx: int):
            return gate.evaluate_execution(
                task_id=task_id,
                power_id=power_id,
                privilege_level=5,
                payload=payload,
                approval_token=token,
            )

        concurrency_level = 50
        with ThreadPoolExecutor(max_workers=concurrency_level) as pool:
            futures = [pool.submit(worker, i) for i in range(concurrency_level)]
            for f in futures:
                allowed, msg, _ = f.result()
                results.append((allowed, msg))

        success_count = sum(1 for allowed, _ in results if allowed is True)
        failure_count = sum(1 for allowed, _ in results if allowed is False)

        assert success_count == 1, f"CRITICAL CONCURRENCY FAILURE: {success_count} threads succeeded (expected 1)!"
        assert failure_count == 49, f"CRITICAL CONCURRENCY FAILURE: {failure_count} threads failed (expected 49)!"

        # Verify all 49 failures cite consumed token or invalid approval
        for allowed, msg in results:
            if not allowed:
                assert "already been consumed" in msg.lower() or "approval failed" in msg.lower()

    def test_cross_power_token_replay_rejected(self):
        """A valid approval token generated for power A cannot be used to execute power B."""
        gate = PolicyGate()
        task_id = f"tsk_crosspwr_{uuid.uuid4().hex[:8]}"
        payload = {"file": "report.pdf"}
        payload_hash = gate.hash_payload(payload)

        # Token generated for benign 'send_email'
        token, _ = gate.generate_approval_token(task_id, "send_email", payload_hash)

        # Attacker attempts to execute destructive 'delete_file' using send_email token
        allowed, msg, _ = gate.evaluate_execution(
            task_id=task_id,
            power_id="delete_file",
            privilege_level=5,
            payload=payload,
            approval_token=token,
        )
        assert allowed is False
        assert "APPROVAL FAILED" in msg
        assert "Invalid cryptographic signature" in msg

    def test_consumed_token_rejected_in_verify_state_approval(self):
        """Tokens already consumed by evaluate_execution must be rejected when queried via verify_state_approval."""
        gate = PolicyGate()
        task_id = f"tsk_state_replay_{uuid.uuid4().hex[:8]}"
        power_id = "kill_process"
        payload = {"pid": 1337}
        payload_hash = gate.hash_payload(payload)

        token, _ = gate.generate_approval_token(task_id, power_id, payload_hash)

        # Execute and consume
        allowed, _, _ = gate.evaluate_execution(
            task_id=task_id, power_id=power_id, privilege_level=5, payload=payload, approval_token=token
        )
        assert allowed is True

        # Now verify_state_approval with the consumed token must fail
        valid, msg = gate.verify_state_approval(
            token=token, task_id=task_id, power_id=power_id, payload_hash=payload_hash
        )
        assert valid is False
        assert "already been consumed" in msg.lower()


# ==============================================================================
# 3. CROSS-USER TOKEN SUBSTITUTION ATTACKS
# ==============================================================================


class TestCrossUserTokenSubstitution:
    """Tests cryptographically enforced identity binding (Alice vs Bob vs Impersonator)."""

    def test_token_generated_for_alice_rejected_for_bob(self):
        """Verify that Alice's HMAC token cannot be used to execute an action on behalf of Bob."""
        gate = PolicyGate()
        task_id = f"tsk_sub_{uuid.uuid4().hex[:8]}"
        power_id = "execute_trade"
        payload = {"ticker": "ETHUSD", "amount": 10.0}
        payload_hash = gate.hash_payload(payload)

        token_alice, _ = gate.generate_approval_token(
            task_id=task_id, power_id=power_id, payload_hash=payload_hash, user_id="alice"
        )

        # Bob attempts execution with Alice's token
        allowed, msg, _ = gate.evaluate_execution(
            task_id=task_id,
            power_id=power_id,
            privilege_level=5,
            payload=payload,
            approval_token=token_alice,
            user_id="bob",
        )
        assert allowed is False
        assert "APPROVAL FAILED" in msg
        assert "Invalid cryptographic signature" in msg

    def test_cross_user_substitution_with_default_admin(self):
        """Alice's token rejected when evaluated under default admin (ganesh), and vice versa."""
        gate = PolicyGate()
        task_id = f"tsk_admin_sub_{uuid.uuid4().hex[:8]}"
        power_id = "format_disk"
        payload = {"target": "D:"}
        payload_hash = gate.hash_payload(payload)

        # Token for ganesh
        token_ganesh, _ = gate.generate_approval_token(
            task_id=task_id, power_id=power_id, payload_hash=payload_hash, user_id="ganesh"
        )

        # Alice attempts execution
        allowed_alice, msg_alice, _ = gate.evaluate_execution(
            task_id=task_id,
            power_id=power_id,
            privilege_level=5,
            payload=payload,
            approval_token=token_ganesh,
            user_id="alice",
        )
        assert allowed_alice is False
        assert "Invalid cryptographic signature" in msg_alice

        # Alice token attempted by ganesh
        token_alice, _ = gate.generate_approval_token(
            task_id=task_id, power_id=power_id, payload_hash=payload_hash, user_id="alice"
        )
        allowed_ganesh, msg_ganesh, _ = gate.evaluate_execution(
            task_id=task_id,
            power_id=power_id,
            privilege_level=5,
            payload=payload,
            approval_token=token_alice,
            user_id="ganesh",
        )
        assert allowed_ganesh is False
        assert "Invalid cryptographic signature" in msg_ganesh

    def test_colon_injection_in_user_id_rejected(self):
        """
        Adversarial delimiter injection: Attacker crafts user_id with colons
        e.g. user_id='alice:tsk_inject:send_email' attempting to align message fields.
        """
        gate = PolicyGate()
        task_id = "tsk_legit"
        power_id = "send_email"
        payload = {"msg": "hello"}
        payload_hash = gate.hash_payload(payload)

        # Attacker crafts malicious user_id containing colons
        malicious_user = "attacker:tsk_legit:format_disk"
        token, _ = gate.generate_approval_token(
            task_id=task_id, power_id=power_id, payload_hash=payload_hash, user_id=malicious_user
        )

        # Attacker tries to execute format_disk under user 'attacker'
        allowed, msg, _ = gate.evaluate_execution(
            task_id=task_id,
            power_id="format_disk",
            privilege_level=5,
            payload=payload,
            approval_token=token,
            user_id="attacker",
        )
        assert allowed is False
        assert "APPROVAL FAILED" in msg


# ==============================================================================
# 4. SIGNATURE AND TIMESTAMP FORGERY ATTACKS
# ==============================================================================


class TestSignatureAndTimestampForgery:
    """Attempts to forge tokens, tamper with timestamps, flip signature bits, or cause type confusion."""

    def test_bit_flip_tampering_rejected(self):
        """Single character change in HMAC signature must deterministically fail."""
        gate = PolicyGate()
        task_id = f"tsk_bitflip_{uuid.uuid4().hex[:8]}"
        power_id = "drop_table"
        payload = {"table": "users"}
        payload_hash = gate.hash_payload(payload)

        token, expiry = gate.generate_approval_token(task_id, power_id, payload_hash)
        sig, exp_str = token.split(".")

        # Flip the first hex character
        flipped_char = "1" if sig[0] != "1" else "2"
        tampered_sig = flipped_char + sig[1:]
        tampered_token = f"{tampered_sig}.{exp_str}"

        valid, reason = gate.verify_approval_token(task_id, power_id, payload_hash, tampered_token)
        assert valid is False
        assert "Invalid cryptographic signature" in reason

    def test_truncated_signature_rejected(self):
        """Signatures with invalid length (e.g. 32 chars instead of 64) must fail."""
        gate = PolicyGate()
        task_id = f"tsk_trunc_{uuid.uuid4().hex[:8]}"
        power_id = "drop_table"
        payload = {"table": "users"}
        payload_hash = gate.hash_payload(payload)

        token, expiry = gate.generate_approval_token(task_id, power_id, payload_hash)
        sig, exp_str = token.split(".")

        # Truncate signature to 32 chars
        truncated_token = f"{sig[:32]}.{exp_str}"
        valid, reason = gate.verify_approval_token(task_id, power_id, payload_hash, truncated_token)
        assert valid is False
        assert "Invalid cryptographic signature" in reason

    def test_future_timestamp_extension_rejected(self):
        """
        Attacker extends token validity by modifying the expiry timestamp into the distant future.
        HMAC signature must reject the tampered expiry!
        """
        gate = PolicyGate()
        task_id = f"tsk_future_{uuid.uuid4().hex[:8]}"
        power_id = "trade_crypto"
        payload = {"asset": "BTC", "qty": 5}
        payload_hash = gate.hash_payload(payload)

        token, expiry = gate.generate_approval_token(task_id, power_id, payload_hash)
        sig, exp_str = token.split(".")

        # Extend timestamp by 1 year (31,536,000 seconds)
        future_expiry = int(exp_str) + 31536000
        tampered_token = f"{sig}.{future_expiry}"

        valid, reason = gate.verify_approval_token(task_id, power_id, payload_hash, tampered_token)
        assert valid is False
        assert "Invalid cryptographic signature" in reason

    def test_expired_token_rejected_immediately(self):
        """Tokens past expiration must be rejected fail-closed without checking HMAC."""
        gate = PolicyGate()
        task_id = f"tsk_exp_{uuid.uuid4().hex[:8]}"
        power_id = "trade_crypto"
        payload = {"asset": "BTC", "qty": 5}
        payload_hash = gate.hash_payload(payload)

        # Synthesize expired token
        past_expiry = int(time.time() - 3600)  # 1 hour ago
        token = f"{'a' * 64}.{past_expiry}"

        valid, reason = gate.verify_approval_token(task_id, power_id, payload_hash, token)
        assert valid is False
        assert "expired" in reason.lower()

    def test_malformed_token_formats_fail_closed_without_exceptions(self):
        """Exotic and malformed token inputs must return False safely without unhandled exceptions."""
        gate = PolicyGate()
        task_id = "tsk_malformed"
        power_id = "delete_file"
        payload_hash = gate.hash_payload({"p": "x"})

        malformed_inputs = [
            "",
            "   ",
            None,
            12345,
            True,
            False,
            [],
            {},
            b"bytes_token",
            "no_dot_at_all",
            ".leading_dot",
            "trailing_dot.",
            "too.many.dots.in.token.12345",
            f"{'a'*64}.not_a_number",
            f"{'a'*64}.12.34",
            f"{'a'*64}.-9999",
            f"{'a'*64}.inf",
            f"{'a'*64}.nan",
            "a" * 64,
            "a" * 10000,  # DoS buffer length
            f"{'a'*64}\x00.{int(time.time() + 600)}",  # Null byte injection
            f"{'a'*64}.{int(time.time() + 600)}\n",  # Newline injection
        ]

        for bad_token in malformed_inputs:
            valid, reason = gate.verify_approval_token(
                task_id, power_id, payload_hash, bad_token  # type: ignore
            )
            assert valid is False, f"Malformed token '{bad_token}' unexpectedly validated!"
            assert isinstance(reason, str)


# ==============================================================================
# 5. FAIL-CLOSED INVARIANTS & AUDIT COMPLIANCE
# ==============================================================================


class TestFailClosedInvariants:
    """Verifies that the policy gate maintains fail-closed security across all emergency paths."""

    def test_kill_switch_unconditionally_overrides_valid_cryptographic_token(self):
        """Even with a 100% valid, unconsumed, user-bound HMAC token, active kill switch halts execution."""
        gate = PolicyGate()
        task_id = f"tsk_kill_{uuid.uuid4().hex[:8]}"
        power_id = "deploy_production"
        payload = {"version": "v3.0.0"}
        payload_hash = gate.hash_payload(payload)

        token, _ = gate.generate_approval_token(task_id, power_id, payload_hash)

        # Activate kill switch
        gate.trigger_kill_switch("Adversarial Emergency Test")
        try:
            assert gate.is_kill_switch_active() is True
            allowed, msg, _ = gate.evaluate_execution(
                task_id=task_id,
                power_id=power_id,
                privilege_level=5,
                payload=payload,
                approval_token=token,
            )
            assert allowed is False
            assert "Emergency Kill Switch is ACTIVE" in msg
            # Token must NOT be consumed if kill switch aborted execution
            assert token not in gate.consumed_tokens
        finally:
            gate.reset_kill_switch()

        # After reset, execution with that token succeeds
        allowed_after, msg_after, _ = gate.evaluate_execution(
            task_id=task_id,
            power_id=power_id,
            privilege_level=5,
            payload=payload,
            approval_token=token,
        )
        assert allowed_after is True

    def test_unregistered_power_with_high_privilege_enforces_approval(self):
        """Any unregistered custom power with privilege >= 3 enforces human approval."""
        gate = PolicyGate()
        task_id = f"tsk_custom_{uuid.uuid4().hex[:8]}"
        payload = {"param": "val"}

        allowed, msg, refusal = gate.evaluate_execution(
            task_id=task_id,
            power_id="unknown_power_custom_99",
            privilege_level=3,
            payload=payload,
        )
        assert allowed is False
        assert "Human approval required" in msg
        assert refusal["status"] == "PENDING"
        assert "token" not in refusal

    def test_strict_isolation_mode_blocks_unapproved_reads(self):
        """When allow_unapproved_reads is False, Privilege Level 1 (reads) must be denied."""
        gate = PolicyGate()
        original_setting = settings.allow_unapproved_reads
        try:
            settings.allow_unapproved_reads = False
            allowed, msg, _ = gate.evaluate_execution(
                task_id="tsk_read_test",
                power_id="read_file",
                privilege_level=1,
                payload={"path": "/data/report.txt"},
            )
            assert allowed is False
            assert "strict isolation mode" in msg.lower()
        finally:
            settings.allow_unapproved_reads = original_setting
