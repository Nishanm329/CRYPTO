"""
Request tracing middleware for distributed tracing support.
Adds X-Request-ID header to all requests for end-to-end request tracking.
"""
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from logging_config import get_logger

logger = get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request tracing.
    Adds X-Request-ID header to request/response for distributed tracing.
    Logs request/response information with timing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with tracing."""
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store request ID in request state for use in handlers
        request.state.request_id = request_id

        # Update logger with request ID
        logger.set_request_id(request_id)

        # Log incoming request
        logger.info(
            f"{request.method} {request.url.path}",
            path=request.url.path,
            method=request.method,
            request_id=request_id,
        )

        # Measure request duration
        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception as e:
            # Log errors
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {str(e)}",
                path=request.url.path,
                method=request.method,
                duration_ms=duration_ms,
                exc_info=True,
                request_id=request_id,
            )
            raise

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log response
        logger.info(
            f"{request.method} {request.url.path} {response.status_code}",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )

        return response


def get_request_id(request: Request) -> str:
    """
    Extract request ID from request state.

    Args:
        request: FastAPI request object

    Returns:
        Request ID string
    """
    return getattr(request.state, "request_id", "unknown")
