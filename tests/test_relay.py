"""
Cross-Device Relay verification (phone <-> laptop).

Covers: pairing lifecycle, token auth, expiry, rate limiting,
TrustResult-backed command execution, and the REST endpoints
(pair / exchange / command / status) via FastAPI TestClient.
"""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.api.routes_relay import router as relay_router
from jarvis.core.relay import DeviceRelay, RelayAuthError, device_relay


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeOrchestrator:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    async def process_user_query(self, query: str):
        self.calls.append(query)
        if self.fail:
            raise RuntimeError("model router offline")
        return {
            "task_id": "tsk_relay_1",
            "status": "COMPLETED",
            "response": {"message": "System health nominal."},
        }


@pytest.fixture()
def relay():
    return DeviceRelay(orchestrator=FakeOrchestrator(), clock=FakeClock())


# --------------------------------------------------------------------- #
#  Unit: pairing lifecycle                                               #
# --------------------------------------------------------------------- #

def test_pairing_code_is_six_digits_and_single_use(relay):
    pair = relay.create_pairing_code(ttl_sec=60)
    assert len(pair["code"]) == 6 and pair["code"].isdigit()
    assert pair["expires_in"] == 60

    first = relay.exchange_code(pair["code"], device_name="pixel")
    assert first["token"] and first["device_id"].startswith("dev_")
    assert first["device_name"] == "pixel"

    with pytest.raises(RelayAuthError):
        relay.exchange_code(pair["code"], device_name="impostor")


def test_expired_pairing_code_rejected(relay):
    clock = relay._clock
    pair = relay.create_pairing_code(ttl_sec=30)
    clock.advance(31)
    with pytest.raises(RelayAuthError, match="expired"):
        relay.exchange_code(pair["code"])


def test_invalid_code_counted_and_rate_limited(relay):
    clock = relay._clock
    for _ in range(8):
        with pytest.raises(RelayAuthError):
            relay.exchange_code("000000")
    # Window must now be locked.
    with pytest.raises(RelayAuthError, match="too many"):
        relay.exchange_code("111111")
    # After the window passes, pairing works again.
    clock.advance(61)
    pair = relay.create_pairing_code()
    result = relay.exchange_code(pair["code"])
    assert result["token"]


def test_authenticate_and_revoke(relay):
    pair = relay.create_pairing_code()
    token = relay.exchange_code(pair["code"])["token"]
    device = relay.authenticate(token)
    assert device["device_name"]

    with pytest.raises(RelayAuthError):
        relay.authenticate("not-a-token")
    with pytest.raises(RelayAuthError):
        relay.authenticate(None)

    assert relay.revoke_device(token) is True
    with pytest.raises(RelayAuthError):
        relay.authenticate(token)
    assert relay.revoke_device(token) is False


# --------------------------------------------------------------------- #
#  Unit: TrustResult-backed execution                                    #
# --------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_execute_command_success_returns_trustresult(relay):
    pair = relay.create_pairing_code()
    token = relay.exchange_code(pair["code"])["token"]

    trust = await relay.execute_command(token, "system health")
    assert trust.verdict == "success"
    trust.assert_evidence_present()
    assert trust.evidence.source == "relay.command"
    assert trust.evidence.data["status"] == "executed"
    assert trust.evidence.data["reply"].startswith("System health")
    assert relay.command_count == 1
    # Evidence log retained (First Law audit trail)
    assert any(e["source"] == "relay.command" for e in relay.evidence_log)


@pytest.mark.asyncio
async def test_execute_command_rejects_bad_token(relay):
    trust = await relay.execute_command("forged-token", "do something")
    assert trust.verdict == "fail"
    assert trust.evidence.data["status"] == "rejected"
    assert relay.command_count == 0


@pytest.mark.asyncio
async def test_execute_command_rejects_empty_command(relay):
    pair = relay.create_pairing_code()
    token = relay.exchange_code(pair["code"])["token"]
    trust = await relay.execute_command(token, "   ")
    assert trust.verdict == "fail"
    assert trust.evidence.data["reason"] == "empty_command"


@pytest.mark.asyncio
async def test_execute_command_orchestrator_failure_is_evidence_backed():
    relay = DeviceRelay(orchestrator=FakeOrchestrator(fail=True), clock=FakeClock())
    pair = relay.create_pairing_code()
    token = relay.exchange_code(pair["code"])["token"]

    trust = await relay.execute_command(token, "anything")
    assert trust.verdict == "fail"
    assert trust.evidence.data["status"] == "error"
    assert "model router offline" in trust.evidence.data["error"]


def test_status_reports_real_counts(relay):
    status = relay.status()
    assert status["paired_devices"] == 0
    assert status["commands_relayed"] == 0
    assert "voice" in status


# --------------------------------------------------------------------- #
#  API: TestClient end-to-end                                            #
# --------------------------------------------------------------------- #

@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(relay_router)
    return TestClient(app)


@pytest.fixture()
def paired_token(relay):
    # Wire the singleton used by the routes to our fake orchestrator/clock.
    original_orch = device_relay._orchestrator
    original_clock = device_relay._clock
    device_relay._orchestrator = relay._orchestrator
    device_relay._clock = relay._clock
    device_relay._pairing.clear()
    device_relay._tokens.clear()
    device_relay._failed_exchanges.clear()
    try:
        yield None
    finally:
        device_relay._orchestrator = original_orch
        device_relay._clock = original_clock
        device_relay._pairing.clear()
        device_relay._tokens.clear()
        device_relay._failed_exchanges.clear()


def test_api_pair_exchange_command_flow(client, paired_token):
    # 1) Laptop mints a code
    res = client.post("/api/v1/relay/pair", json={"ttl_sec": 120})
    assert res.status_code == 200
    code = res.json()["code"]
    assert len(code) == 6

    # 2) Phone exchanges it for a token
    res = client.post("/api/v1/relay/exchange", json={"code": code, "device_name": "pixel"})
    assert res.status_code == 200
    token = res.json()["token"]
    assert token

    # 3) Phone sends a command with Bearer auth
    res = client.post(
        "/api/v1/relay/command",
        json={"command": "system health"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["verdict"] == "success"
    assert body["evidence"]["source"] == "relay.command"
    assert body["evidence"]["data"]["reply"].startswith("System health")

    # 4) Status endpoint works with the same token
    res = client.get(
        "/api/v1/relay/status", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    status = res.json()
    assert status["device"]["device_name"] == "pixel"
    assert status["relay"]["commands_relayed"] == 1
    assert "voice" in status["relay"]


def test_api_command_requires_auth(client, paired_token):
    res = client.post("/api/v1/relay/command", json={"command": "hi"})
    assert res.status_code == 401
    res = client.post(
        "/api/v1/relay/command",
        json={"command": "hi"},
        headers={"Authorization": "Bearer bogus"},
    )
    assert res.status_code == 401


def test_api_bad_exchange_rejected(client, paired_token):
    res = client.post("/api/v1/relay/exchange", json={"code": "999999"})
    assert res.status_code == 401


def test_api_relay_page_served(client, paired_token):
    res = client.get("/relay")
    assert res.status_code == 200
    assert "JARVIS" in res.text
    assert "PAIR" in res.text
