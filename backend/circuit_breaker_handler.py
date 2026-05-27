"""
Circuit Breaker Pattern for Binance API Resilience

Prevents cascading failures when Binance API is down by:
1. Tracking consecutive failures
2. Opening circuit to fail fast (not wait for timeout)
3. Periodically testing if service recovered (half-open)
4. Closing circuit once service is healthy
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, Any, List
from enum import Enum
from logging_config import get_logger

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failing fast
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreakerException(Exception):
    """Raised when circuit is OPEN (service unavailable)."""
    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    Transition diagram:
    CLOSED --[consecutive_failures >= threshold]--> OPEN
    OPEN --[timeout elapsed]--> HALF_OPEN
    HALF_OPEN --[test succeeds]--> CLOSED
    HALF_OPEN --[test fails]--> OPEN (reset timeout)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: int = 60,
        expected_exception: type = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name (for logging)
            failure_threshold: Consecutive failures before opening (default 3)
            recovery_timeout_seconds: Seconds before testing recovery (default 60s)
            expected_exception: Exception type to catch and count (default Exception)
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        self.expected_exception = expected_exception

        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None

    def is_open(self) -> bool:
        """Check if circuit is OPEN and we should fail immediately."""
        if self.state == CircuitState.OPEN:
            # Check if we should transition to HALF_OPEN (timeout elapsed)
            if self.opened_at and (datetime.utcnow() - self.opened_at) >= self.recovery_timeout:
                logger.info(
                    f"Circuit breaker {self.name}: OPEN → HALF_OPEN (testing recovery)",
                    action="circuit_half_open",
                    circuit=self.name,
                )
                self.state = CircuitState.HALF_OPEN
                return False  # Allow test request
            return True  # Still open, fail fast
        return False

    def record_success(self):
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            # Recovery succeeded, close circuit
            logger.info(
                f"Circuit breaker {self.name}: HALF_OPEN → CLOSED (recovered)",
                action="circuit_closed",
                circuit=self.name,
            )
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None

        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            if self.failure_count > 0:
                logger.debug(
                    f"Circuit breaker {self.name}: success, resetting failure count",
                    action="circuit_success",
                    circuit=self.name,
                    prev_failures=self.failure_count,
                )
            self.failure_count = 0
            self.last_failure_time = None

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            # Recovery test failed, reopen circuit
            logger.warning(
                f"Circuit breaker {self.name}: HALF_OPEN → OPEN (recovery test failed)",
                action="circuit_reopened",
                circuit=self.name,
            )
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()

        elif self.state == CircuitState.CLOSED:
            # Check if we reached failure threshold
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker {self.name}: CLOSED → OPEN ({self.failure_count} consecutive failures)",
                    action="circuit_opened",
                    circuit=self.name,
                    failure_count=self.failure_count,
                )
                self.state = CircuitState.OPEN
                self.opened_at = datetime.utcnow()
            else:
                logger.warning(
                    f"Circuit breaker {self.name}: failure {self.failure_count}/{self.failure_threshold}",
                    action="circuit_failure",
                    circuit=self.name,
                    failure_count=self.failure_count,
                )

    def get_status(self) -> dict:
        """Get circuit breaker status."""
        return {
            "circuit": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }


class CircuitBreakerPolicy:
    """Retry and circuit breaker policy for API calls."""

    def __init__(
        self,
        circuit_breaker: CircuitBreaker,
        max_retries: int = 3,
        initial_delay_ms: int = 100,
        max_delay_ms: int = 2000,
    ):
        """
        Initialize retry policy.

        Args:
            circuit_breaker: Circuit breaker instance
            max_retries: Maximum retry attempts (default 3)
            initial_delay_ms: Initial retry delay in ms (default 100)
            max_delay_ms: Maximum retry delay in ms (default 2000)
        """
        self.circuit_breaker = circuit_breaker
        self.max_retries = max_retries
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms

    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute function with circuit breaker and retries.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerException: If circuit is OPEN
            Exception: If all retries exhausted
        """
        # Check circuit state
        if self.circuit_breaker.is_open():
            logger.error(
                f"Circuit breaker {self.circuit_breaker.name} is OPEN",
                action="circuit_open_fail_fast",
                circuit=self.circuit_breaker.name,
            )
            raise CircuitBreakerException(
                f"Circuit breaker {self.circuit_breaker.name} is OPEN. Service unavailable."
            )

        # Try with retries
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                self.circuit_breaker.record_success()
                return result

            except self.circuit_breaker.expected_exception as e:
                last_exception = e
                self.circuit_breaker.record_failure()

                if attempt < self.max_retries:
                    # Calculate exponential backoff
                    delay_ms = min(
                        self.initial_delay_ms * (2 ** attempt),
                        self.max_delay_ms,
                    )
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries + 1} failed, retrying in {delay_ms}ms",
                        action="retry_with_backoff",
                        circuit=self.circuit_breaker.name,
                        attempt=attempt + 1,
                        delay_ms=delay_ms,
                        error=str(e),
                    )
                    await asyncio.sleep(delay_ms / 1000)
                else:
                    logger.error(
                        f"All retries exhausted for {self.circuit_breaker.name}",
                        action="retries_exhausted",
                        circuit=self.circuit_breaker.name,
                        max_retries=self.max_retries,
                        error=str(e),
                    )

        # Raise last exception after retries exhausted
        raise last_exception


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        """Initialize circuit breaker registry."""
        self.breakers: dict[str, CircuitBreaker] = {}
        self.policies: dict[str, CircuitBreakerPolicy] = {}

    def register(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: int = 60,
        expected_exception: type = Exception,
        max_retries: int = 3,
    ) -> CircuitBreakerPolicy:
        """
        Register a new circuit breaker.

        Args:
            name: Circuit breaker name
            failure_threshold: Failures before opening
            recovery_timeout_seconds: Timeout before half-open
            expected_exception: Exception type to catch
            max_retries: Retry attempts

        Returns:
            CircuitBreakerPolicy for this breaker
        """
        breaker = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=recovery_timeout_seconds,
            expected_exception=expected_exception,
        )
        policy = CircuitBreakerPolicy(
            circuit_breaker=breaker,
            max_retries=max_retries,
        )

        self.breakers[name] = breaker
        self.policies[name] = policy

        logger.info(
            f"Registered circuit breaker: {name}",
            action="circuit_registered",
            circuit=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout_seconds,
        )

        return policy

    def get_policy(self, name: str) -> Optional[CircuitBreakerPolicy]:
        """Get policy for a circuit breaker."""
        return self.policies.get(name)

    def get_status_all(self) -> List[dict]:
        """Get status of all circuit breakers."""
        return [breaker.get_status() for breaker in self.breakers.values()]

    def reset_all(self):
        """Reset all circuit breakers (for testing)."""
        for breaker in self.breakers.values():
            breaker.state = CircuitState.CLOSED
            breaker.failure_count = 0
            breaker.last_failure_time = None
            breaker.opened_at = None
            logger.info(
                f"Reset circuit breaker: {breaker.name}",
                action="circuit_reset",
                circuit=breaker.name,
            )


# Global registry
_registry: Optional[CircuitBreakerRegistry] = None


def get_registry() -> CircuitBreakerRegistry:
    """Get or create global circuit breaker registry."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()

        # Register default circuit breakers for Binance APIs
        _registry.register(
            "binance_price_fetch",
            failure_threshold=3,
            recovery_timeout_seconds=30,
            max_retries=2,
        )
        _registry.register(
            "binance_order_placement",
            failure_threshold=2,
            recovery_timeout_seconds=60,
            max_retries=1,
        )
        _registry.register(
            "binance_order_status",
            failure_threshold=3,
            recovery_timeout_seconds=30,
            max_retries=2,
        )

    return _registry
