"""
Prometheus metrics collection for API monitoring.
Tracks request counts, durations, errors, and business metrics.
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import time
from functools import wraps
from typing import Callable, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


# Create registry for metrics
registry = CollectorRegistry()

# Request metrics
request_count = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

request_duration = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0),
    registry=registry,
)

request_size = Histogram(
    "api_request_size_bytes",
    "API request size in bytes",
    ["method", "endpoint"],
    registry=registry,
)

response_size = Histogram(
    "api_response_size_bytes",
    "API response size in bytes",
    ["method", "endpoint"],
    registry=registry,
)

# Error metrics
error_count = Counter(
    "api_errors_total",
    "Total API errors",
    ["method", "endpoint", "error_type"],
    registry=registry,
)

# Business metrics
signal_count = Counter(
    "signals_generated_total",
    "Total signals generated",
    ["symbol", "timeframe", "direction"],
    registry=registry,
)

scan_duration = Histogram(
    "scan_duration_seconds",
    "Market scan duration in seconds",
    ["timeframe"],
    buckets=(1, 5, 10, 30, 60, 120),
    registry=registry,
)

pairs_scanned = Gauge(
    "pairs_scanned_count",
    "Number of pairs scanned",
    registry=registry,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Collect metrics for request/response."""
        # Extract endpoint (path without query params)
        endpoint = request.url.path

        # Measure request size
        request_body_size = 0
        if request.method in ["POST", "PUT", "PATCH"]:
            request_body_size = len(await request.body())

        # Measure request duration
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Record metrics
        request_count.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
        ).inc()

        request_duration.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        if request_body_size > 0:
            request_size.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(request_body_size)

        # Try to get response size (may not always work with streaming responses)
        try:
            response_body_size = int(response.headers.get("content-length", 0))
            if response_body_size > 0:
                response_size.labels(
                    method=request.method,
                    endpoint=endpoint,
                ).observe(response_body_size)
        except (ValueError, TypeError):
            pass

        # Record errors
        if 400 <= response.status_code < 600:
            error_type = "client_error" if 400 <= response.status_code < 500 else "server_error"
            error_count.labels(
                method=request.method,
                endpoint=endpoint,
                error_type=error_type,
            ).inc()

        return response


def track_signal(symbol: str, direction: str, timeframe: str = "1h") -> None:
    """
    Record a signal generation event.

    Args:
        symbol: Trading pair symbol
        direction: Signal direction (LONG, SHORT, NEUTRAL)
        timeframe: Timeframe of the signal
    """
    signal_count.labels(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
    ).inc()


def track_scan(timeframe: str, duration_seconds: float, pair_count: int) -> None:
    """
    Record a market scan event.

    Args:
        timeframe: Scan timeframe
        duration_seconds: Scan duration in seconds
        pair_count: Number of pairs scanned
    """
    scan_duration.labels(timeframe=timeframe).observe(duration_seconds)
    pairs_scanned.set(pair_count)


def metrics_timer(func: Callable) -> Callable:
    """
    Decorator to measure function execution time.
    Useful for tracking long-running operations.

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            return await func(*args, **kwargs)
        finally:
            duration = time.time() - start_time
            # Could emit custom metrics here
            pass

    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            duration = time.time() - start_time
            # Could emit custom metrics here
            pass

    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
