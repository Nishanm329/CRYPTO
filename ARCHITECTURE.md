# Architecture Overview

Complete system architecture for CryptoSignal AI trading signals platform.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser / Client                          │
│                    (Next.js Frontend)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTPS (SSL/TLS)
                             │
┌─────────────────────────────────────────────────────────────────┐
│                    Nginx Reverse Proxy                           │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ • SSL/TLS Termination                                      │ │
│  │ • API Rate Limiting                                        │ │
│  │ • Security Headers (HSTS, CSP, X-Frame-Options)           │ │
│  │ • Static File Caching                                      │ │
│  │ • Load Balancing (frontend + backend)                      │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────────┬──────────────────────────────┬────────────────────┘
             │                              │
             ▼                              ▼
    ┌─────────────────────┐       ┌─────────────────────┐
    │   Next.js Frontend  │       │  FastAPI Backend    │
    │   Port: 3000        │       │   Port: 8000        │
    │                     │       │                     │
    │ • React Components  │       │ • Signal Generation │
    │ • Trading Charts    │       │ • Market Scanning   │
    │ • Backtesting UI    │       │ • Backtesting Engine│
    │ • Error Boundaries  │       │ • API Endpoints     │
    │ • Sentry Tracking   │       │ • Request Logging   │
    └──────────┬──────────┘       └─────────┬───────────┘
               │                            │
               └─────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────────┐   ┌──────────────┐   ┌───────────────┐
   │ PostgreSQL  │   │ TimescaleDB  │   │ Redis Cache   │
   │ Database    │   │ (Hypertable) │   │ (Optional)    │
   │             │   │              │   │               │
   │ • Users     │   │ • Signals    │   │ • Sessions    │
   │ • Prefs     │   │ • History    │   │ • Rate Limits │
   │ • Settings  │   │ • Analytics  │   │ • Temp Data   │
   └─────────────┘   └──────────────┘   └───────────────┘
```

## Detailed Component Architecture

### Frontend (Next.js)

```
frontend/
├── pages/
│   ├── _app.js              # App wrapper, Sentry init, Theme
│   ├── _document.js         # HTML structure
│   ├── index.js             # Dashboard (main page)
│   ├── scan.js              # Market scan results
│   ├── backtest.js          # Backtesting interface
│   └── settings.js          # User preferences
│
├── components/
│   ├── ErrorBoundary.js     # React error boundary
│   ├── TradingChart.js      # lightweight-charts wrapper
│   ├── SignalCard.js        # Signal display component
│   ├── StatsStrip.js        # Market stats header
│   ├── RightPanel.js        # Chart indicators panel
│   └── Header.js            # Navigation
│
├── lib/
│   ├── api.js               # API client (auto includes Bearer token)
│   ├── sentry-config.js     # Error tracking
│   └── utils.js             # Formatting, helpers
│
├── public/                  # Static assets
├── styles/                  # Tailwind CSS
└── .env.local              # Local environment (API_KEY, API_URL)
```

**Technology Stack:**
- Next.js 14 (React framework)
- Tailwind CSS (styling)
- lightweight-charts (charting)
- Sentry (error tracking)
- SWR (data fetching)

---

### Backend (FastAPI)

```
backend/
├── main.py                  # FastAPI app, endpoints
├── config.py                # Configuration management
├── models.py                # Pydantic + SQLAlchemy models
├── db.py                    # Database connection
├── repositories.py          # Data access layer
├── security.py              # API key auth, quota management
│
├── Core Logic:
│   ├── signal.py            # Signal generation
│   ├── indicators.py        # Technical indicators (EMA, RSI, MACD, etc)
│   ├── binance_client.py    # Binance API wrapper
│   ├── scanner.py           # Market scanning logic
│   └── backtester.py        # Backtest engine
│
├── Infrastructure:
│   ├── logging_config.py    # JSON structured logging
│   ├── request_tracing.py   # X-Request-ID header propagation
│   ├── metrics.py           # Prometheus metrics
│   ├── circuit_breaker.py   # Binance API resilience
│   └── validators.py        # Input validation
│
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_validators.py
│   ├── test_circuit_breaker.py
│   └── test_api_endpoints.py
│
├── requirements.txt         # Dependencies
├── Dockerfile              # Container definition
├── pytest.ini              # Test configuration
└── Makefile               # Development commands
```

**Technology Stack:**
- FastAPI (async web framework)
- Pydantic (data validation)
- SQLAlchemy (ORM)
- PostgreSQL/TimescaleDB (database)
- Prometheus (metrics)
- Structlog (logging)

---

### Database Schema

```
PostgreSQL + TimescaleDB
│
├── signals_history (hypertable, time-series)
│   ├── id (serial primary key)
│   ├── symbol (varchar, indexed)
│   ├── timeframe (varchar)
│   ├── direction (varchar: LONG/SHORT)
│   ├── confidence (0-100)
│   ├── entry_price (float)
│   ├── stop_loss (float)
│   ├── take_profits (JSON array)
│   ├── indicators (JSON array)
│   ├── sentiment_score (float)
│   ├── pnl_pct (float, null until closed)
│   ├── is_closed (boolean, indexed)
│   ├── created_at (timestamptz, indexed)
│   └── closed_at (timestamptz)
│
├── user_preferences
│   ├── id (serial primary key)
│   ├── user_id (varchar unique)
│   ├── alert_symbols (JSON array)
│   ├── alert_timeframes (JSON array)
│   ├── alert_min_confidence (int)
│   ├── preferred_timeframes (JSON array)
│   ├── dark_mode (boolean)
│   ├── chart_type (varchar)
│   └── api_key_last_used (timestamptz)
│
└── error_logs
    ├── id (serial primary key)
    ├── error_code (varchar)
    ├── error_message (varchar)
    ├── error_stack (varchar)
    ├── source (varchar: frontend/backend)
    ├── user_id (varchar, indexed)
    ├── request_id (varchar, indexed)
    ├── context (JSON object)
    └── created_at (timestamptz, indexed)
```

---

### Data Flow Diagram

```
Signal Generation Flow:

User Request (/api/signal/BTCUSDT)
  ↓
[Authentication Layer]
  • Validate API key
  • Check quota
  ↓
[Request Tracing]
  • Generate X-Request-ID
  • Start timing
  ↓
[Input Validation]
  • Validate symbol (regex)
  • Validate timeframe
  ↓
[Fetch Candles]
  • Binance API (get_klines)
  • [Circuit Breaker] handles failures
  ↓
[Calculate Indicators]
  • EMA 7, EMA 25 (trend)
  • RSI (momentum)
  • MACD (momentum)
  • Bollinger Bands (volatility)
  • VWAP (support/resistance)
  ↓
[Sentiment]
  • Fear & Greed Index
  ↓
[Signal Generation]
  • Check EMA cross
  • Multi-indicator confluence
  • Calculate confidence score
  • AI probability (ML model)
  ↓
[Store in Database]
  • signals_history table
  • Track performance
  ↓
[Logging]
  • Log request duration
  • Log metrics (Prometheus)
  ↓
[Response]
  • Return to user
  • Include X-Request-ID
```

---

### Request Lifecycle

```
1. Browser sends request with Bearer token
   GET /api/signal/BTCUSDT
   Authorization: Bearer demo-key-public

2. Nginx reverse proxy
   • Check SSL certificate
   • Rate limit by IP
   • Forward to backend

3. FastAPI receives request
   • RequestTracingMiddleware: Generate X-Request-ID
   • MetricsMiddleware: Start timing
   • CORS: Validate origin

4. Authentication
   • get_current_user dependency
   • Validate API key
   • Check quota
   • Update last_used timestamp

5. Handler function
   • Validate inputs (symbol, timeframe)
   • Fetch candles from Binance
   • Calculate indicators
   • Generate signal
   • Store in database
   • Increment metrics

6. Response
   • Serialize JSON
   • Include timing headers
   • Add security headers (Nginx)
   • Return to browser

7. Browser
   • Parse response
   • Update UI
   • Log to Sentry if error
```

---

### Deployment Architecture

```
Production Deployment (docker-compose.prod.yml):

┌──────────────────────────────────────────────────┐
│                Internet / DNS                     │
│            cryptosignal.com                       │
└────────────────────┬─────────────────────────────┘
                     │ :80, :443
                     ▼
         ┌──────────────────────┐
         │   Nginx Container    │
         │ • SSL termination    │
         │ • Reverse proxy      │
         │ • Load balance       │
         └────────┬─────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
   ┌────────────┐      ┌────────────┐
   │  Frontend  │      │  Backend   │
   │ :3000      │      │  :8000     │
   └────────────┘      └─────┬──────┘
                             │
                   ┌─────────┼─────────┐
                   │         │         │
                   ▼         ▼         ▼
            ┌──────────┐ ┌───────┐ ┌──────────┐
            │PostgreSQL│ │Redis  │ │Binance   │
            │:5432     │ │:6379  │ │API       │
            └──────────┘ └───────┘ └──────────┘
```

---

## External APIs

### Binance API (Market Data)

```
GET https://api.binance.com/api/v3/klines
├── Parameters: symbol, interval, limit
├── Returns: OHLCV candles
└── RateLimit: 1200 requests/minute

Circuit Breaker handles:
  • Connection timeouts
  • Rate limiting (429 response)
  • Server errors (5xx)
```

### Fear & Greed Index API

```
GET https://api.alternative.me/fng
├── Returns: Daily fear/greed score (0-100)
├── Cache: 1 request/day
└── Fallback: Return neutral (50) on error
```

---

## Error Handling Strategy

```
Error Boundaries:
  │
  ├─ Frontend (React)
  │  ├─ ErrorBoundary component
  │  ├─ Try-catch in async functions
  │  └─ Sentry error tracking
  │
  ├─ API (FastAPI)
  │  ├─ HTTPException for known errors
  │  ├─ Validation errors (400)
  │  ├─ Auth errors (401)
  │  └─ Rate limits (429)
  │
  ├─ External APIs
  │  ├─ Circuit breaker (fail fast)
  │  ├─ Retry with exponential backoff
  │  └─ Fallback values
  │
  └─ Database
     ├─ Connection pooling
     ├─ Retry logic
     └─ Transaction rollback
```

---

## Security Layers

```
1. Network Level
   ├─ HTTPS/SSL/TLS (Nginx termination)
   ├─ Security headers (HSTS, CSP, X-Frame-Options)
   └─ Rate limiting (IP-based)

2. API Level
   ├─ Bearer token authentication
   ├─ API key validation
   ├─ Quota enforcement (daily limits)
   ├─ Input validation (regex, bounds)
   └─ CORS (domain whitelist)

3. Database Level
   ├─ Parameterized queries (SQL injection protection)
   ├─ Connection pooling
   ├─ Row-level security (per-user preferences)
   └─ Encryption at rest (managed by cloud provider)

4. Application Level
   ├─ Error handling (no stack traces exposed)
   ├─ Logging (sensitive data masked)
   ├─ Dependency scanning (CVE detection)
   └─ Code review (pre-commit hooks)
```

---

## Scalability Strategy

### Horizontal Scaling

```
Multiple backend instances:
  • Load balance with Nginx
  • Shared database (PostgreSQL)
  • Shared cache (Redis)
  • Stateless design (no session affinity needed)

Kubernetes scaling:
  • Auto-scale based on CPU/memory
  • Rolling updates (zero downtime)
  • Health check endpoints
  • Readiness probes
```

### Vertical Scaling

```
Backend:
  • Increase worker processes (WORKERS env var)
  • Optimize database queries
  • Add caching layer (Redis)
  • Connection pooling (DB_POOL_SIZE)

Database:
  • TimescaleDB hypertables for compression
  • Partitioning by time
  • Index optimization
  • Read replicas for analytics
```

### Caching Strategy

```
Frontend:
  • HTTP caching (Cache-Control headers)
  • SWR for data deduplication
  • localStorage for preferences

Backend:
  • Redis for quota tracking
  • HTTP caching for public endpoints
  • In-memory caches for expensive calculations
```

---

## Monitoring & Observability

### Metrics (Prometheus)

```
Request Metrics:
  • requests_total (by method, path, status)
  • request_duration_seconds (histogram)
  • request_size_bytes (histogram)
  • response_size_bytes (histogram)

Business Metrics:
  • signals_generated_total (by symbol, direction)
  • scan_duration_seconds (histogram)
  • backtest_combinations_tested (gauge)

Error Metrics:
  • errors_total (by error_code)
  • circuit_breaker_state (open, closed, half-open)
```

### Logging (Structured JSON)

```
Log Fields:
  • timestamp (ISO8601)
  • level (INFO, WARNING, ERROR, DEBUG)
  • logger (module name)
  • message (human-readable)
  • request_id (X-Request-ID header)
  • user_id (if authenticated)
  • path, method, status_code (for requests)
  • duration_ms (request time)
  • error, stack (for exceptions)
  • context (custom fields)
```

### Tracing (Request ID)

```
X-Request-ID Propagation:
  Browser → Nginx → Backend → Database
  
  All logs, metrics, and errors include request_id
  Allows correlation of entire request lifecycle
```

---

## Disaster Recovery

### Backup Strategy

```
Database:
  • Automated daily backups (PostgreSQL)
  • Backup retention: 30 days
  • Backup location: S3/Cloud Storage
  • Test restore monthly

Code:
  • Git repository (GitHub)
  • Multiple branches (main, develop)
  • Release tags (semantic versioning)
```

### Failover Strategy

```
High Availability:
  • Multiple backend instances
  • Load balancer health checks
  • Database replication
  • Cache replication (Redis)

Recovery:
  • RTO (Recovery Time Objective): <5 minutes
  • RPO (Recovery Point Objective): <1 hour
  • Automated health checks
  • Alert on failures
```

---

## Development Workflow

```
1. Developer Creates Branch
   git checkout -b feature/new-signal

2. Pre-Commit Hooks Run
   • Code formatting (Black, Prettier)
   • Linting (flake8, ESLint)
   • Type checking (mypy)
   • Security checks

3. Push & Create PR
   • GitHub Actions runs tests
   • Backend: pytest, coverage
   • Frontend: Jest, coverage

4. Code Review
   • Automated checks pass
   • Peers review changes
   • Approved & merged

5. CI/CD Pipeline
   • Tests run again
   • Docker images built
   • Deploy to staging
   • Smoke tests

6. Version Tag for Production
   git tag v1.2.3
   • Automatic production deploy
   • Database backup
   • Health checks
```

---

## Key Design Principles

✅ **Separation of Concerns**
- Frontend (presentation), Backend (logic), Database (data)

✅ **Stateless Design**
- Enables horizontal scaling
- No session affinity needed

✅ **Fail Fast**
- Input validation early
- Circuit breaker for external APIs
- Clear error messages

✅ **Observability**
- Structured logging
- Distributed tracing (request IDs)
- Prometheus metrics
- Error tracking (Sentry)

✅ **Security By Default**
- HTTPS/SSL
- API key authentication
- Quota enforcement
- Input validation

✅ **Resilience**
- Retry logic with exponential backoff
- Circuit breaker pattern
- Fallback values
- Database transactions

✅ **Performance**
- Caching strategy
- Database optimization
- Async operations
- CDN for static files
