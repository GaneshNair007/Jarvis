"""
JARVIS Integration Retry Policy
Implements exponential backoff with jitter and error classification.
Differentiates between transient network/concurrency failures vs permanent authorization/parameter errors.
"""

import time
import random
from typing import Callable, Any, Optional, Set, Type

class RetryPolicy:
    """Configurable exponential backoff policy for external service integration calls."""

    DEFAULT_RETRYABLE_STATUSES: Set[int] = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay_sec: float = 0.5,
        backoff_multiplier: float = 2.0,
        max_delay_sec: float = 10.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Set[Type[Exception]]] = None
    ):
        self.max_retries = max_retries
        self.initial_delay_sec = initial_delay_sec
        self.backoff_multiplier = backoff_multiplier
        self.max_delay_sec = max_delay_sec
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or {
            TimeoutError,
            ConnectionError,
            ConnectionResetError,
            OSError
        }

    def is_retryable(self, error: Exception) -> bool:
        """Determines if an exception is transient and safe to retry."""
        # Policy denial or auth failure must NEVER be retried
        err_msg = str(error).lower()
        if any(unretryable in err_msg for unretryable in ["unauthorized", "forbidden", "denied", "invalid_grant", "policy_halt"]):
            return False

        # Status code checking if available
        status_code = getattr(error, "status_code", None) or getattr(error, "code", None)
        if isinstance(status_code, int):
            return status_code in self.DEFAULT_RETRYABLE_STATUSES

        # Exception type checking
        return any(isinstance(error, exc_type) for exc_type in self.retryable_exceptions)

    def calculate_delay(self, attempt: int) -> float:
        """Computes exponential backoff delay with optional random jitter."""
        delay = self.initial_delay_sec * (self.backoff_multiplier ** attempt)
        delay = min(delay, self.max_delay_sec)
        if self.jitter:
            delay = delay * (0.8 + 0.4 * random.random())
        return round(delay, 3)

    def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Executes a callable with automatic retries for transient errors."""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt == self.max_retries or not self.is_retryable(e):
                    raise e
                delay = self.calculate_delay(attempt)
                time.sleep(delay)
        if last_error:
            raise last_error

# Global standard retry policy
default_retry_policy = RetryPolicy()
