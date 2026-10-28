"""
Automated Test Suite for OpenRouter Free Model Integration
Verifies:
  1. OpenRouterClient configuration, headers, and zero-cost model discovery
  2. Structured response parsing (content, reasoning trace, reasoning tokens, usage metrics)
  3. Strawberry test verification ('How many r\'s are in strawberry?')
  4. Automatic 429 rate limit retry and fallback model routing
  5. OpenRouterIntegration lifecycle, BaseIntegration contract, and power execution
"""

import pytest
from unittest.mock import patch, MagicMock
from integrations.openrouter.client import (
    OpenRouterClient,
    openrouter_client,
    OpenRouterResponse,
    OpenRouterUsage,
)
from integrations.openrouter.openrouter_integration import OpenRouterIntegration
from integrations.base.integration_registry import integration_registry


def test_openrouter_client_headers_and_defaults():
    client = OpenRouterClient(api_key="test-key-openrouter", default_model="openrouter/free")
    headers = client._get_headers()
    assert headers["Authorization"] == "Bearer test-key-openrouter"
    assert "JARVIS AI OS" in headers["X-Title"]
    assert client.default_model == "openrouter/free"


def test_openrouter_get_free_models():
    client = OpenRouterClient()
    mock_payload = {
        "data": [
            {"id": "meta-llama/llama-3.3-70b:free", "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "paid-model/gpt-5", "pricing": {"prompt": "0.01", "completion": "0.03"}},
            {"id": "google/gemma-4-31b-it:free", "pricing": {"prompt": "0", "completion": "0"}},
        ]
    }
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        models = client.get_free_models(force_refresh=True)
        assert "meta-llama/llama-3.3-70b:free" in models
        assert "google/gemma-4-31b-it:free" in models
        assert "openrouter/free" in models
        assert "paid-model/gpt-5" not in models


def test_openrouter_chat_completion_with_reasoning():
    client = OpenRouterClient(api_key="mock-key")
    mock_response_data = {
        "id": "gen-test-12345",
        "model": "xingchen-agi/xing4.0-29b-a4b:free",
        "provider": "Phala",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "There are 3 r's in the word 'strawberry'.",
                    "reasoning": "Step 1: s-t-r(1)-a-w-b-e-r(2)-r(3)-y. Total count: 3.",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 18,
            "completion_tokens": 250,
            "total_tokens": 268,
            "cost": 0.0,
            "completion_tokens_details": {"reasoning_tokens": 235},
        },
    }

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        mock_post.return_value = mock_resp

        res = client.chat_completion(
            messages=[{"role": "user", "content": "How many r's are in the word 'strawberry'?"}]
        )

        assert isinstance(res, OpenRouterResponse)
        assert "3" in res.content
        assert res.reasoning is not None
        assert "s-t-r" in res.reasoning
        assert res.usage.reasoning_tokens == 235
        assert res.fallback_used is False  # Candidate requested was 'openrouter/free' which succeeded
        assert res.model == "xingchen-agi/xing4.0-29b-a4b:free"


def test_openrouter_rate_limit_fallback():
    client = OpenRouterClient(api_key="mock-key")
    # First candidate (openrouter/free) returns 429, second candidate (liquid/lfm-2.5-2.6b:free) succeeds
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "upstream pool rate limited"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "id": "gen-fallback-1",
        "model": "liquid/lfm-2.5-2.6b:free",
        "choices": [{"message": {"role": "assistant", "content": "Success via fallback model."}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20, "cost": 0.0},
    }

    with patch("httpx.Client.post", side_effect=[resp_429, resp_429, resp_429, resp_200]):
        with patch("time.sleep", return_value=None):
            res = client.chat_completion(
                messages=[{"role": "user", "content": "Test"}],
                max_retries=3,
                enable_fallbacks=True,
            )
            assert res.model == "liquid/lfm-2.5-2.6b:free"
            assert "Success" in res.content
            assert res.fallback_used is True


def test_openrouter_integration_lifecycle_and_powers():
    integ = OpenRouterIntegration()
    assert integ.integration_id == "openrouter"
    assert integ.default_approval_tier == 0
    assert integ.cost_model == "free"

    # List powers
    powers = integ.list_powers()
    pids = [p["power_id"] for p in powers]
    assert "openrouter.chat" in pids
    assert "openrouter.list_free_models" in pids
    assert "openrouter.test_reasoning" in pids

    # Connect with credentials
    integ.connect({"OPENROUTER_API_KEY": "test-token-valid-abc"})
    assert integ.connected is True
    integ.enable()
    assert integ.enabled is True

    # Test power execution
    with patch.object(integ.client, "get_free_models", return_value=["openrouter/free", "liquid/lfm-2.5-2.6b:free"]):
        exec_result = integ.execute_power("openrouter.list_free_models", {})
        assert exec_result["status"] == "SUCCESS"
        assert exec_result["result"]["count"] == 2
        assert "openrouter/free" in exec_result["result"]["free_models"]

    # Health check
    report = integ.health_check()
    assert report.connected is True
    assert report.enabled is True
