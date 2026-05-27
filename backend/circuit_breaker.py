"""
Circuit breaker pattern for external API resilience.
Prevents cascading failures by failing fast when services are unhealthy.
"""
from datetime import datetime, timedelta
from typing import Callable, Any, Optional
from enum import Enum
import asyncio


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation, requests pass through
    OPEN = "open"           # Failing, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    States:
    - CLOSED: Normal state, requests pass through and update stats
    - OPEN: Service is down, fail fast without making requests
    - HALF_OPEN: Testing recovery, allow one request to test the service

    Transition logic:
    - CLOSED -> OPEN: After failure_threshold failures
    - OPEN -> HALF_OPEN: After timeout_seconds elapsed
    - HALF_OPEN -> CLOSED: If test request succeeds
    - HALF_OPEN -> OPEN: If test request fails
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60,
        name: str = "CircuitBreaker",
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures to open circuit
            success_threshold: Number of successes in HALF_OPEN to close circuit
            timeout_seconds: Seconds before OPEN -> HALF_OPEN transition
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.name = name

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_open_time: Optional[datetime] = None

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker (sync version).

        Args:
            func: Callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of func() if circuit is CLOSED or HALF_OPEN

        Raises:
            CircuitBreakerOpen: If circuit is OPEN
            Exception: Any exception raised by func()
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                print(f"[{self.name}] Circuit HALF_OPEN, attempting reset", flush=True)
            else:
                raise CircuitBreakerOpen(f"{self.name} circuit is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute async function through circuit breaker.

        Args:
            func: Async callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of await func() if circuit is CLOSED or HALF_OPEN

        Raises:
            CircuitBreakerOpen: If circuit is OPEN
            Exception: Any exception raised by func()
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                print(f"[{self.name}] Circuit HALF_OPEN, attempting reset", flush=True)
            else:
                raise CircuitBreakerOpen(f"{self.name} circuit is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Record successful call."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                print(f"[{self.name}] Circuit CLOSED, service recovered", flush=True)
        else:
            self.success_count = 0

    def _on_failure(self) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.last_open_time = datetime.now()
            print(f"[{self.name}] Circuit OPEN, service still unhealthy", flush=True)
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_open_time = datetime.now()
            print(f"[{self.name}] Circuit OPEN after {self.failure_count} failures", flush=True)

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_open_time is None:
            return True
        elapsed = (datetime.now() - self.last_open_time).total_seconds()
        return elapsed >= self.timeout_seconds

    def reset(self) -> None:
        """Force reset circuit to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_open_time = None
        print(f"[{self.name}] Circuit manually reset to CLOSED", flush=True)

    def get_state(self) -> dict:
        """Get circuit breaker state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_open_time": self.last_open_time.isoformat() if self.last_open_time else None,
        }


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is in OPEN state."""
    pass
