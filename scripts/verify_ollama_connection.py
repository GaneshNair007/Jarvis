"""Verify that JARVIS can reach its configured Ollama model and get a reply.

Run from the repository root:
    python scripts/verify_ollama_connection.py

This performs a real inference request. It never prints credentials or sign-in
material and exits non-zero unless Ollama returns a non-empty response.
"""
from __future__ import annotations

import sys
import time

import httpx

from jarvis.config import settings


def _normalise_model_name(value: str) -> str:
    name = str(value or "").strip().lower()
    if name and ":" not in name.rsplit("/", 1)[-1]:
        name = f"{name}:latest"
    return name


def main() -> int:
    base_url = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_default_model.strip()
    if not model:
        print("FAIL: OLLAMA_DEFAULT_MODEL is empty.")
        return 2

    try:
        tags_response = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        tags_response.raise_for_status()
        tags_payload = tags_response.json()
    except Exception as exc:
        print(f"FAIL: Ollama model inventory is unavailable at {base_url}: {type(exc).__name__}: {exc}")
        print("Start the Ollama app/service and confirm OLLAMA_BASE_URL.")
        return 1

    entries = tags_payload.get("models") if isinstance(tags_payload, dict) else None
    if not isinstance(entries, list):
        print("FAIL: Ollama /api/tags did not return a valid models list.")
        return 1

    available_models = sorted(
        {
            str(item.get("name") or item.get("model")).strip()
            for item in entries
            if isinstance(item, dict) and (item.get("name") or item.get("model"))
        }
    )
    if _normalise_model_name(model) not in {_normalise_model_name(name) for name in available_models}:
        print(f"FAIL: Configured model '{model}' is not available in this Ollama instance.")
        print("Available models: " + (", ".join(available_models) if available_models else "(none)"))
        print("Pull/select the model, then update OLLAMA_DEFAULT_MODEL in .env.")
        return 1

    started = time.perf_counter()
    try:
        inference_response = httpx.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": "Reply with exactly: JARVIS_OLLAMA_OK",
                "stream": False,
            },
            timeout=settings.ollama_timeout_sec,
        )
        inference_response.raise_for_status()
        result = inference_response.json()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 401:
            print("FAIL: Ollama rejected the cloud-model request. Sign in with 'ollama signin' and retry.")
        elif status_code == 402:
            print("FAIL: Ollama reports that this cloud model requires a plan or usage credits.")
        elif status_code == 404:
            print(f"FAIL: Ollama could not find model '{model}'. Check its exact tag.")
        else:
            print(f"FAIL: Ollama inference returned HTTP {status_code}: {exc.response.text[:300]}")
        return 1
    except Exception as exc:
        print(f"FAIL: Ollama inference did not complete: {type(exc).__name__}: {exc}")
        return 1

    reply = result.get("response", "").strip() if isinstance(result, dict) else ""
    if not reply:
        print("FAIL: Ollama returned an empty response; JARVIS is not verified.")
        return 1

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    print("PASS: JARVIS reached Ollama and received a real model response.")
    print(f"Endpoint: {base_url}")
    print(f"Model: {model}")
    print(f"Latency: {elapsed_ms:.1f} ms")
    print(f"Response: {reply[:240]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
