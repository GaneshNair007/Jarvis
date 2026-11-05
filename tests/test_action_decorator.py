"""Tests for ActionWeaver-style Action Decorator."""

from jarvis.core.action_decorator import action
from jarvis.core.power_binder import power_binder


def test_action_decorator_wraps_and_registers():
    @action(
        name="custom_math_multiplier",
        description="Multiplies two numbers",
        category="math",
        keywords=["multiply", "product"],
    )
    def multiply(a: int, b: int) -> int:
        return a * b

    # Direct invocation
    assert multiply(3, 4) == 12

    # Verify registered in power_binder
    assert "custom_math_multiplier" in power_binder._tools
    schema = power_binder._tools["custom_math_multiplier"]["schema"]
    assert schema["type"] == "function"
    assert "a" in schema["function"]["parameters"]["properties"]
    assert "b" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["properties"]["a"]["type"] == "integer"


def test_action_execution_via_power_binder():
    @action(
        name="custom_greeting",
        description="Greets a user with title",
    )
    def greet(name: str, formal: bool = False) -> str:
        prefix = "Greetings" if formal else "Hello"
        return f"{prefix}, {name}!"

    res = power_binder.execute_tool("custom_greeting", {"name": "Ganesh", "formal": True})
    assert res["success"] is True
    assert res["result"] == "Greetings, Ganesh!"
