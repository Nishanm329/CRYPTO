# Logging & Monitoring Guide (Phase 3)

This guide explains the logging, monitoring, and error tracking infrastructure for CryptoSignal AI.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Sentry Integration (sentry-config.js)                      │ │
│  │ - Unhandled errors captured                                │ │
│  │ - Promise rejections tracked                               │ │
│  │ - Breadcrumbs for debugging                                │ │
│  │ - Error reports sent to backend /api/errors                │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────┬──────────────────────────────────────────────┘
                     │ HTTP Requests
┌────────────────────▼──────────────────────────────────────────────┐
│                    Backend (FastAPI)                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Request Tracing Middleware (request_tracing.py)            │ │
│  │ - Generates/forwards X-Request-ID headers                  │ │
│  │ - Logs request/response with timing                        │ │
│  │ - Tracks duration and status codes                         │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Structured JSON Logging (logging_config.py)                │ │
│  │ - All logs as JSON for machine parsing                     │ │
│  │ - Includes request context (ID, path, status, duration)    │ │
│  │ - Timezone: UTC, ISO 8601 format                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Metrics Collection (metrics.py)                            │ │
│  │ - Prometheus metrics for monitoring                        │ │
│  │ - Request counts, latencies, error rates                   │ │
│  │ - Business metrics (signals generated, pairs scanned)      │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## 1. Structured JSON Logging (Backend)

### Features

- **JSON Format**: All logs are JSON for easy parsing and indexing
- **Request Context**: Automatic inclusion of request_id, path, method, status
- **Timestamps**: ISO 8601 format (UTC)
- **Exception Info**: Includes exception type and message

### Example Log Output

```json
{
  "timestamp": "2026-05-09T13:44:56.556889Z",
  "level": "INFO",
  "logger": "__main__",
  "message": "GET /api/chart/BTCUSDT 200",
  "module": "request_tracing",
  "function": "dispatch",
  "line": 45,
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "path": "/api/chart/BTCUSDT",
  "method": "GET",
  "status_code": 200,
  "duration_ms": 145.32
}
```

### Usage

```python
from logging_config import get_logger

logger = get_logger(__name__)

# Simple info log
logger.info("Processing market scan")

# Log with request context
logger.info(
    "Chart data fetched",
    path="/api/chart/BTCUSDT",
    method="GET",
    status_code=200,
    duration_ms=145.32,
)

# Log errors
logger.error("Failed to fetch Binance data", exc_info=True)

# Debug logging
logger.debug("Cache hit for symbol", symbol="BTCUSDT")
```

### Configuration

Set log level via `LOG_LEVEL` environment variable:

```bash
LOG_LEVEL=DEBUG    # Verbose, includes all debug messages
LOG_LEVEL=INFO     # Normal, includes info and above
LOG_LEVEL=WARNING  # Only warnings and errors
LOG_LEVEL=ERROR    # Only errors
```

## 2. Request Tracing (Backend)

### Features

- **X-Request-ID Header**: Unique ID for each request, included in all logs
- **Request/Response Logging**: Automatic logging of all API calls
- **Timing Measurement**: Request duration tracked in milliseconds
- **Request Forwarding**: Client-provided X-Request-ID headers are preserved

### Example Request/Response

```
Request:
  X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
  GET /api/signal/BTCUSDT?timeframe=1h

Response:
  X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
  200 OK (Duration: 234.45ms)
```

### Usage in Handlers

```python
from request_tracing import get_request_id
from fastapi import Request

@app.get("/api/example")
async def example_endpoint(request: Request):
    request_id = get_request_id(request)
    logger.info("Processing request", request_id=request_id)
    return {"request_id": request_id}
```

### Frontend Integration

Send X-Request-ID when making API calls:

```javascript
const requestId = crypto.randomUUID();
const response = await fetch("/api/signal/BTCUSDT", {
  headers: {
    "X-Request-ID": requestId,
  },
});
```

## 3. Prometheus Metrics

### Exposed Metrics

Access at `http://localhost:8000/metrics`

#### Request Metrics

```
api_requests_total{method="GET",endpoint="/api/chart",status="200"} 152
api_request_duration_seconds{method="GET",endpoint="/api/chart"} [histogram]
api_request_size_bytes{method="POST",endpoint="/api/scan"} [histogram]
api_response_size_bytes{method="GET",endpoint="/api/chart"} [histogram]
api_errors_total{method="GET",endpoint="/api/signal",error_type="server_error"} 3
```

#### Business Metrics

```
signals_generated_total{symbol="BTCUSDT",timeframe="1h",direction="LONG"} 24
scan_duration_seconds{timeframe="1h"} [histogram]
pairs_scanned_count 450
```

### Prometheus Configuration

Add to your Prometheus `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cryptosignal'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Grafana Dashboard

Create a Grafana dashboard to visualize:

1. **Request Rate**: `rate(api_requests_total[1m])`
2. **Error Rate**: `rate(api_errors_total[1m])`
3. **Latency**: `histogram_quantile(0.95, api_request_duration_seconds)`
4. **Signals Generated**: `signals_generated_total`

## 4. Frontend Error Tracking (Sentry)

### Setup

1. **Create Sentry Account**: https://sentry.io (free tier available)

2. **Configure Environment Variable**:
   ```bash
   NEXT_PUBLIC_SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0
   ```

3. **Initialize**: Automatically done in `_app.js`

### Error Capture

The system automatically captures:

- **Unhandled Errors**: JavaScript exceptions
- **Promise Rejections**: Unhandled async errors
- **Error Boundary Errors**: React component errors
- **API Errors**: Failed fetch/axios requests

### Manual Error Reporting

```javascript
import { reportError, addBreadcrumb } from "@/lib/sentry-config";

try {
  await fetchData();
} catch (error) {
  // Report to backend error logger
  reportError(error, { context: "fetchData" });
}

// Add breadcrumbs for debugging
addBreadcrumb("User clicked button", "user-action");
addBreadcrumb("Navigating to settings", "navigation");
```

### Error Response Format

Errors sent to backend at `POST /api/errors`:

```json
{
  "message": "Failed to fetch chart data",
  "stack": "Error: Network timeout\n    at fetchData (chart.js:123)",
  "type": "Error",
  "timestamp": "2026-05-09T13:44:56.556Z",
  "userAgent": "Mozilla/5.0...",
  "url": "http://localhost:3000/chart",
  "context": {
    "symbol": "BTCUSDT",
    "timeframe": "1h"
  }
}
```

## 5. Monitoring Stack Integration

### All Components Together

```
Frontend Errors
    ↓
  /api/errors (backend logs to structured JSON)
    ↓
Structured JSON Logs (stdout)
    ↓
Log Aggregation Service (ELK, Splunk, Datadog, etc.)
    ↓
Dashboards & Alerts

Request Tracing
    ↓
Request Logs (JSON with request_id)
    ↓
Log Aggregation
    ↓
Distributed Tracing Visualization

Metrics
    ↓
Prometheus Scraping
    ↓
Grafana Dashboards
    ↓
Alerts & Notifications
```

### Production Deployment Checklist

- [ ] Enable LOG_LEVEL=INFO in production
- [ ] Configure Sentry with real DSN
- [ ] Set up Prometheus scraping
- [ ] Create Grafana dashboards
- [ ] Configure log aggregation (ELK, Splunk, etc.)
- [ ] Set up alerting rules for errors (>5 errors/min)
- [ ] Set up alerting for high latency (p95 > 1s)
- [ ] Set up alerting for circuit breakers opening
- [ ] Monitor rate limiting hits
- [ ] Archive logs for compliance

## 6. Troubleshooting

### No logs appearing

1. Check `LOG_LEVEL` environment variable
2. Verify middleware is initialized in correct order
3. Check log output in `stdout`

### Request ID not propagating

1. Verify middleware is added to app (order matters - add early)
2. Check client is sending `X-Request-ID` header
3. Verify header name is exact (case-sensitive)

### Metrics not updating

1. Check `/metrics` endpoint returns data
2. Verify Prometheus is scraping the endpoint
3. Check for errors in Prometheus logs

### Errors not captured on frontend

1. Verify `NEXT_PUBLIC_SENTRY_DSN` is set
2. Check browser console for initialization errors
3. Verify error triggers (unhandled exceptions, not try/catch)

## 7. Next Steps

- Phase 4: Testing (pytest, Jest integration tests)
- Phase 5: Database Persistence (PostgreSQL + TimescaleDB)
- Phase 6: Authentication (API keys, rate limiting per user)
- Phase 7: Production Configuration (Docker, Nginx, env management)
