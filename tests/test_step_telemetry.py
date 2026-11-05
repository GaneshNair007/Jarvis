"""Tests for Step Telemetry and Streaming Manager."""

from jarvis.core.step_telemetry import StepTelemetryManager


def test_step_telemetry_lifecycle():
    telemetry = StepTelemetryManager()
    task_id = "test_task_001"

    # 1. Start root step
    root_step = telemetry.start_step(task_id, "Plan Task", step_type="plan")
    assert root_step.status == "running"

    # 2. Start child tool step
    tool_step = telemetry.start_step(
        task_id,
        "Execute Calculator",
        step_type="tool",
        parent_id=root_step.step_id,
        inputs={"operation": "add"},
    )
    assert tool_step.parent_id == root_step.step_id

    # 3. Complete tool step
    tool_step.complete({"result": 42})
    assert tool_step.status == "completed"
    assert tool_step.output == {"result": 42}
    assert tool_step.end_time is not None

    # 4. Root step complete
    root_step.complete({"summary": "Done"})

    # 5. Retrieve steps
    steps = telemetry.get_steps(task_id)
    assert len(steps) == 2
    assert steps[0]["name"] == "Plan Task"
    assert steps[1]["name"] == "Execute Calculator"
    assert steps[1]["duration_ms"] >= 0


def test_step_telemetry_approval_wait():
    telemetry = StepTelemetryManager()
    task_id = "test_task_002"

    step = telemetry.start_step(task_id, "Send Outbound Email", step_type="approval")
    step.wait_for_approval({"token_required": True, "action": "email.send"})

    assert step.status == "pending_approval"
    steps = telemetry.get_steps(task_id)
    assert steps[0]["output"]["token_required"] is True
