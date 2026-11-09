"""Tests for OpenAI Assistants API Compatibility Routes."""

from fastapi.testclient import TestClient
from jarvis.api.server import app

client = TestClient(app)


def test_list_assistants():
    res = client.get("/v1/assistants")
    assert res.status_code == 200
    data = res.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 1
    assert data["data"][0]["id"] == "asst_jarvis_core"


def test_create_thread_and_messages():
    # 1. Create thread
    res = client.post("/v1/threads", json={})
    assert res.status_code == 200
    thread = res.json()
    thread_id = thread["id"]
    assert thread_id.startswith("thread_")

    # 2. Add message to thread
    res_msg = client.post(
        f"/v1/threads/{thread_id}/messages",
        json={"role": "user", "content": "What is the CPU usage?"},
    )
    assert res_msg.status_code == 200
    msg = res_msg.json()
    assert msg["role"] == "user"

    # 3. List messages
    res_list = client.get(f"/v1/threads/{thread_id}/messages")
    assert res_list.status_code == 200
    msgs = res_list.json()["data"]
    assert len(msgs) == 1


def test_create_thread_run():
    # 1. Create thread
    t_res = client.post("/v1/threads", json={})
    thread_id = t_res.json()["id"]

    # 2. Post prompt message
    client.post(
        f"/v1/threads/{thread_id}/messages",
        json={"role": "user", "content": "system status"},
    )

    # 3. Create run
    run_res = client.post(f"/v1/threads/{thread_id}/runs", json={})
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "completed"

    # 4. Check that assistant message was appended
    msgs_res = client.get(f"/v1/threads/{thread_id}/messages")
    messages = msgs_res.json()["data"]
    assert any(m["role"] == "assistant" for m in messages)
