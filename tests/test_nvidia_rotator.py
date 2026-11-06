"""
Unit Tests for the NVIDIA NIM Key Rotator (TIER_3_CLOUD frontier gateway).
Tests:
  1. Multi-key discovery precedence (NVIDIA_API_KEYS, NVIDIA_KEY_1..N, NVIDIA_API_KEY)
  2. Round-robin rotation with 429 cooldown failover
  3. Key redaction — raw credentials never surface in telemetry
  4. Honest availability behavior (no keys -> no requests -> no fake claims)
  5. Integration surface: APIKeyRotatorManager summary + model_router status
"""

import json
import urllib.error
from unittest.mock import patch

import pytest

from jarvis.core.api_key_rotator import (
    NvidiaNimKeyRotator,
    APIKeyRotatorManager,
)


class TestNvidiaNimKeyDiscovery:
    def test_discovery_from_comma_separated_keys(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEYS", "nvapi_key_one, nvapi_key_two")
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        rotator = NvidiaNimKeyRotator()

        assert rotator.key_count >= 2
        assert "nvapi_key_one" in rotator.keys
        assert "nvapi_key_two" in rotator.keys

    def test_discovery_from_numbered_and_primary_keys(self, monkeypatch):
        for var in ["NVIDIA_API_KEYS"]:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("NVIDIA_KEY_1", "nvapi_numbered_1")
        monkeypatch.setenv("NVIDIA_KEY_2", "nvapi_numbered_2")
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi_primary")
        rotator = NvidiaNimKeyRotator()

        assert rotator.key_count == 3
        assert "nvapi_numbered_1" in rotator.keys
        assert "nvapi_primary" in rotator.keys

    def test_metrics_never_leak_raw_keys(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEYS", "nvapi_secret_alpha,nvapi_secret_beta")
        rotator = NvidiaNimKeyRotator()
        metrics = rotator.get_metrics()

        assert metrics["provider"] == "nvidia_nim"
        dumped = json.dumps(metrics)
        assert "nvapi_secret_alpha" not in dumped  # First Law: credentials stay masked
        assert "nvapi_secret_beta" not in dumped
        assert all("..." in k["key"] for k in metrics["keys"])

    def test_no_keys_is_honestly_unavailable(self, monkeypatch):
        for var in ["NVIDIA_API_KEYS", "NVIDIA_API_KEY", "NVIDIA_KEY_1"]:
            monkeypatch.delenv(var, raising=False)
        rotator = NvidiaNimKeyRotator()
        assert not rotator.is_available
        # No keys -> no request -> no fabricated success
        assert rotator.generate_chat_completion("test prompt") is None


class TestNvidiaNimFailover:
    def _fake_success_response(self):
        resp = json.dumps({
            "choices": [{"message": {"content": "JARVIS online. Verified."}}],
            "usage": {"total_tokens": 42},
        }).encode("utf-8")

        class FakeResp:
            status = 200

            def read(self):
                return resp

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return FakeResp()

    def test_429_rotates_to_next_key(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEYS", "nvapi_k1,nvapi_k2")
        rotator = NvidiaNimKeyRotator()

        call_count = {"n": 0}

        def fake_urlopen(req, timeout=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "Rate Limited", {}, None)
            return self._fake_success_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = rotator.generate_chat_completion("What is the status, JARVIS?")

        assert result is not None
        assert result["status"] == "success"
        assert result["provider"] == "nvidia_nim"
        assert nvidia_redacted_not_raw(result)  # key_used must be masked
        assert rotator.get_tracker("nvapi_k1").rate_limit_429_count == 1
        assert rotator.get_tracker("nvapi_k2").successful_requests == 1


def nvidia_redacted_not_raw(result):
    """Helper predator for First Law: result may reference a key only in redacted form."""
    raw = [k for k in result.values() if isinstance(k, str)]
    assert not any(k.startswith("nvapi_") and "..." not in k for k in raw), "raw key leaked"
    return True


class TestRotatorManagerIntegration:
    def test_manager_summary_includes_nvidia(self):
        manager = APIKeyRotatorManager()
        summary = manager.get_summary()
        assert "nvidia_nim" in summary
        assert summary["nvidia_nim"]["provider"] == "nvidia_nim"

    def test_model_router_status_includes_nvidia(self):
        from jarvis.core.model_router import model_router

        status = model_router.get_status()
        assert "nvidia_nim_available" in status["tier_3_cloud"]
        assert "nvidia_nim" in status["tier_3_cloud"]["key_rotator_summary"]
        assert "nvidia_nim" in status["tier_3_cloud"]["circuit_breakers"]
