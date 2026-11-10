"""Unit tests for FreeLLMAPI Client."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from jarvis.core.freellmapi_client import FreeLLMAPIClient


def test_freellmapi_client_initialization():
    client = FreeLLMAPIClient()
    assert client.base_url.startswith("http://localhost:3001")
    assert client.default_model == "auto"


@patch("urllib.request.urlopen")
def test_freellmapi_is_available_true(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    client = FreeLLMAPIClient()
    assert client.is_available is True


@patch("urllib.request.urlopen")
def test_freellmapi_generate_completion_success(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    sample_response = {
        "model": "qwen/qwen3.8-27b",
        "choices": [{"message": {"role": "assistant", "content": "I am online and ready."}}],
        "usage": {"total_tokens": 15},
    }
    mock_resp.read.return_value = json.dumps(sample_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    client = FreeLLMAPIClient()
    res = client.generate_completion(prompt="Hello Jarvis")

    assert res is not None
    assert res["status"] == "success"
    assert res["reply"] == "I am online and ready."
    assert res["model"] == "qwen/qwen3.8-27b"
    assert res["tokens_used"] == 15


@patch("urllib.request.urlopen")
def test_freellmapi_generate_completion_http_error(mock_urlopen):
    import urllib.error

    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="http://localhost:3001/v1/chat/completions",
        code=500,
        msg="Internal Error",
        hdrs={},
        fp=MagicMock(read=lambda: b"Server Error"),
    )

    client = FreeLLMAPIClient()
    res = client.generate_completion(prompt="Hello Jarvis")
    assert res is None
