"""
Unit tests for circuit breaker pattern.
"""
import pytest
import asyncio
from circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpen,
)


class TestCircuitBreakerStates:
    """Tests for circuit breaker state transitions."""

    def test_initial_state_closed(self):
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_closed_to_open_transition(self):
        """Circuit should open after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        def failing_func():
            raise ValueError("Test error")

        # Fail 3 times
        for i in range(3):
            with pytest.raises(ValueError):
                cb.call(failing_func)

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_open_circuit_fails_fast(self):
        """Circuit breaker should fail fast when OPEN."""
        cb = CircuitBreaker(failure_threshold=1)

        def failing_func():
            raise ValueError("Test error")

        # Trigger OPEN state
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Next call should fail immediately without calling function
        with pytest.raises(CircuitBreakerOpen):
            cb.call(failing_func)

    def test_open_to_half_open_transition(self):
        """Circuit should move to HALF_OPEN after timeout."""
        import time

        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1)

        def failing_func():
            raise ValueError("Test error")

        # Trigger OPEN state
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.1)

        # Next call should attempt reset (transition to HALF_OPEN for test)
        # but since the function still fails, it transitions back to OPEN
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN  # Failed test call returns to OPEN

    def test_half_open_to_closed_on_success(self):
        """Circuit should close on successful call in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, success_threshold=1)

        def failing_func():
            raise ValueError("Test error")

        # Trigger OPEN state
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Force HALF_OPEN for testing
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 0

        # Successful call should close circuit
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        """Circuit should reopen on failure in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1)

        # Force HALF_OPEN state
        cb.state = CircuitState.HALF_OPEN

        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """Successful call should reset failure count in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3)

        def failing_func():
            raise ValueError("Test error")

        def success_func():
            return "success"

        # Fail once
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.failure_count == 1

        # Success should reset failure count
        cb.call(success_func)
        assert cb.failure_count == 0


class TestAsyncCircuitBreaker:
    """Tests for async circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_async_call_success(self):
        """Async successful call should work."""
        cb = CircuitBreaker()

        async def async_func():
            return "success"

        result = await cb.call_async(async_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_call_failure(self):
        """Async failure should be handled."""
        cb = CircuitBreaker(failure_threshold=1)

        async def async_failing_func():
            raise ValueError("Async error")

        with pytest.raises(ValueError):
            await cb.call_async(async_failing_func)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_async_open_circuit_fails_fast(self):
        """Async open circuit should fail fast."""
        cb = CircuitBreaker(failure_threshold=1)

        async def async_failing_func():
            raise ValueError("Async error")

        # Trigger OPEN
        with pytest.raises(ValueError):
            await cb.call_async(async_failing_func)

        # Should fail fast
        with pytest.raises(CircuitBreakerOpen):
            await cb.call_async(async_failing_func)


class TestCircuitBreakerMonitoring:
    """Tests for circuit breaker monitoring capabilities."""

    def test_get_state(self):
        """Get state should return monitoring data."""
        cb = CircuitBreaker(name="test_breaker")
        state = cb.get_state()

        assert state["name"] == "test_breaker"
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["success_count"] == 0

    def test_manual_reset(self):
        """Manual reset should return circuit to CLOSED."""
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        cb.failure_count = 5

        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0


class TestCircuitBreakerConfiguration:
    """Tests for circuit breaker configuration."""

    def test_custom_failure_threshold(self):
        """Custom failure threshold should be respected."""
        cb = CircuitBreaker(failure_threshold=5)

        def failing_func():
            raise ValueError("Test error")

        # Fail 4 times - should still be CLOSED
        for _ in range(4):
            with pytest.raises(ValueError):
                cb.call(failing_func)

        assert cb.state == CircuitState.CLOSED

        # Fail 5th time - should transition to OPEN
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

    def test_custom_success_threshold(self):
        """Custom success threshold should be respected."""
        cb = CircuitBreaker(success_threshold=3)
        cb.state = CircuitState.HALF_OPEN

        def success_func():
            return "success"

        # Succeed 2 times - should still be HALF_OPEN
        for _ in range(2):
            cb.call(success_func)

        assert cb.state == CircuitState.HALF_OPEN

        # Succeed 3rd time - should transition to CLOSED
        cb.call(success_func)
        assert cb.state == CircuitState.CLOSED
