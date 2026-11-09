"""ActionWeaver-inspired Action Decorator for Project Jarvis.

Provides pythonic declarative function wrapping with automatic JSON Schema generation,
type hint extraction, parameter validation, and dynamic registration into PowerBinder.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Dict, List, Optional, TypeVar

from jarvis.core.logger import get_logger
from jarvis.core.power_binder import power_binder

logger = get_logger("core.action_decorator")

F = TypeVar("F", bound=Callable[..., Any])


class Action:
    """Represents an executable action with typed parameter schema."""

    def __init__(
        self,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "general",
        keywords: Optional[List[str]] = None,
        privilege_level: int = 1,
    ):
        self.func = func
        self.name = name or func.__name__
        self.description = description or func.__doc__ or f"Action {self.name}"
        self.category = category
        self.keywords = keywords or [self.name.replace("_", " ")]
        self.privilege_level = privilege_level
        self.schema = self._build_schema()

        # Update wrapper metadata
        functools.update_wrapper(self, func)

    def _build_schema(self) -> Dict[str, Any]:
        """Infers OpenAI function-calling JSON schema from Python type annotations."""
        sig = inspect.signature(self.func)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = "string"
            if param.annotation is int:
                param_type = "integer"
            elif param.annotation is float:
                param_type = "number"
            elif param.annotation is bool:
                param_type = "boolean"
            elif param.annotation in (dict, Dict[str, Any]):
                param_type = "object"
            elif param.annotation in (list, List[str], List[Any]):
                param_type = "array"

            properties[param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}",
            }
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description.strip(),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)


def action(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "custom",
    keywords: Optional[List[str]] = None,
    privilege_level: int = 1,
    register: bool = True,
) -> Callable[[F], Action]:
    """Decorator converting standard Python functions into discoverable JARVIS actions."""

    def decorator(fn: F) -> Action:
        act = Action(
            func=fn,
            name=name,
            description=description,
            category=category,
            keywords=keywords,
            privilege_level=privilege_level,
        )
        if register:
            power_binder.register_function(
                name=act.name,
                func=act.func,
                description=act.description,
                category=act.category,
                keywords=act.keywords,
                privilege_level=act.privilege_level,
            )
            logger.debug("Registered action %s into PowerBinder", act.name)
        return act

    return decorator
