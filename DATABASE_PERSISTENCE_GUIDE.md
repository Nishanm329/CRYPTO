# Database Persistence Guide (Phase 5)

Comprehensive guide for signal history tracking and user preferences persistence using PostgreSQL + TimescaleDB.

## Overview

```
Signal Generation (Backend)
        ↓
   Store in DB ← PostgreSQL + TimescaleDB
        ↓
   User Preferences ← Per-user settings
        ↓
   Performance Analysis ← Historical data
```

## Architecture

### Database Schema

#### signals_history
Stores every signal generated for performance tracking.

```sql
CREATE TABLE signals_history (
  id SERIAL PRIMARY KEY,
  symbol VARCHAR(20) NOT NULL,
  timeframe VARCHAR(10) NOT NULL,
  direction VARCHAR(10) NOT NULL,  -- LONG or SHORT
  confidence INTEGER NOT NULL,      -- 0-100
  ai_probability FLOAT NOT NULL,
  entry_price FLOAT NOT NULL,
  stop_loss FLOAT NOT NULL,
  take_profits JSON NOT NULL,       -- List of TP levels
  rr_ratio FLOAT NOT NULL,
  indicators JSON NOT NULL,         -- Indicator confirmations
  sentiment_score FLOAT,
  volume_ratio FLOAT,
  atr FLOAT,
  
  -- Performance tracking (updated when signal resolves)
  entry_executed_price FLOAT,
  exit_price FLOAT,
  exit_reason VARCHAR(50),          -- STOP_LOSS, TP1, TP2, etc.
  pnl_pct FLOAT,                    -- Realized P&L percentage
  is_closed BOOLEAN DEFAULT false,
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at TIMESTAMPTZ,
  
  INDEX (symbol, created_at),
  INDEX (is_closed)
);
```

#### user_preferences
Stores user settings and alert configurations.

```sql
CREATE TABLE user_preferences (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(100) UNIQUE NOT NULL,
  
  -- Alert settings
  alert_symbols JSON DEFAULT '[]',
  alert_timeframes JSON DEFAULT '[]',
  alert_min_confidence INTEGER DEFAULT 60,
  
  -- Display settings
  preferred_timeframes JSON DEFAULT '["1h", "4h", "1d"]',
  preferred_symbols JSON DEFAULT '[]',
  chart_type VARCHAR(20) DEFAULT 'candlestick',
  dark_mode BOOLEAN DEFAULT false,
  
  -- Strategy settings
  preferred_strategy VARCHAR(50) DEFAULT 'ema_cross',
  max_drawdown_tolerance FLOAT DEFAULT 20.0,
  min_win_rate FLOAT DEFAULT 40.0,
  
  api_key_last_used TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  INDEX (user_id)
);
```

#### error_logs
Stores frontend and backend errors for monitoring.

```sql
CREATE TABLE error_logs (
  id SERIAL PRIMARY KEY,
  error_code VARCHAR(50) NOT NULL,
  error_message VARCHAR(500) NOT NULL,
  error_stack VARCHAR(5000),
  
  source VARCHAR(20) NOT NULL,    -- frontend or backend
  endpoint VARCHAR(200),
  user_id VARCHAR(100),
  request_id VARCHAR(36),
  
  context JSON DEFAULT '{}',
  status_code INTEGER,
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  INDEX (user_id),
  INDEX (request_id),
  INDEX (created_at)
);
```

### TimescaleDB Hypertable

For large-scale time-series data, convert `signals_history` to a hypertable:

```sql
SELECT create_hypertable('signals_history', 'created_at', if_not_exists => TRUE);
CREATE INDEX signals_history_symbol_time ON signals_history (symbol, created_at DESC);
```

TimescaleDB automatically compresses and chunks historical data, improving query performance for large datasets.

## Database Models (SQLAlchemy ORM)

### SignalHistoryDB

```python
from models import SignalHistoryDB

# All attributes:
signal = SignalHistoryDB(
    symbol="BTCUSDT",
    timeframe="1h",
    direction="LONG",
    confidence=85,
    ai_probability=0.87,
    entry_price=45000.00,
    stop_loss=44000.00,
    take_profits=[...],  # JSON
    rr_ratio=2.5,
    indicators=[...],    # JSON
    sentiment_score=0.3,
    volume_ratio=1.5,
    atr=500.0,
)
```

### UserPreferencesDB

```python
from models import UserPreferencesDB

prefs = UserPreferencesDB(
    user_id="user_123",
    alert_symbols=["BTCUSDT", "ETHUSDT"],
    alert_timeframes=["1h", "4h"],
    alert_min_confidence=75,
    dark_mode=True,
    chart_type="candlestick",
)
```

## Database Repository Operations

### SignalRepository

#### Store a Generated Signal

```python
from repositories import SignalRepository
from db import SessionLocal

db = SessionLocal()
db_signal = SignalRepository.store_signal(db, signal)
# Returns: SignalHistoryDB with id auto-assigned
```

#### Get Recent Signals

```python
# All signals
signals = SignalRepository.get_recent_signals(db, limit=50)

# Filter by symbol
btc_signals = SignalRepository.get_recent_signals(db, symbol="BTCUSDT", limit=100)
```

#### Update Signal Exit

```python
# When signal closes (hits stop loss or take profit)
SignalRepository.update_signal_exit(
    db,
    signal_id=42,
    exit_price=45500.00,
    exit_reason="TP1",  # or "STOP_LOSS", "TP2", etc.
    pnl_pct=3.33,  # +3.33% profit
)
```

#### Get Performance Statistics

```python
stats = SignalRepository.get_performance_stats(db)
# Returns:
# {
#   "total_trades": 45,
#   "win_rate": 64.44,
#   "avg_pnl": 1.23,
#   "best_trade": 5.67,
#   "worst_trade": -2.15,
#   "winning_trades": 29,
#   "losing_trades": 16,
# }

# Or filter by symbol
btc_stats = SignalRepository.get_performance_stats(db, symbol="BTCUSDT")
```

### UserRepository

#### Get or Create Preferences

```python
from repositories import UserRepository

prefs = UserRepository.get_or_create_preferences(db, user_id="user_123")
# Automatically creates defaults if user doesn't exist
```

#### Update Alert Settings

```python
# Update symbols
UserRepository.update_alert_symbols(db, "user_123", ["BTCUSDT", "ETHUSDT"])

# Update timeframes
UserRepository.update_alert_timeframes(db, "user_123", ["1h", "4h", "1d"])

# Update minimum confidence
UserRepository.update_alert_min_confidence(db, "user_123", 80)
```

#### Update Display Preferences

```python
UserRepository.update_display_preferences(
    db,
    user_id="user_123",
    dark_mode=True,
    chart_type="candlestick"
)
```

### ErrorRepository

#### Store an Error

```python
from repositories import ErrorRepository

ErrorRepository.store_error(
    db,
    error_code="INVALID_SYMBOL",
    error_message="Symbol INVALID not found",
    source="backend",
    endpoint="/api/signal/INVALID",
    user_id="user_123",
    request_id="req-456",
    status_code=400,
)
```

#### Get Recent Errors

```python
# All errors
errors = ErrorRepository.get_recent_errors(db, limit=100)

# Filter by source
backend_errors = ErrorRepository.get_recent_errors(db, source="backend", limit=50)
```

#### Get Error Frequency

```python
# Error counts in last 24 hours by error_code
frequency = ErrorRepository.get_error_frequency(db, hours=24)
# Returns: {"INVALID_SYMBOL": 12, "RATE_LIMITED": 5, ...}
```

## API Endpoints

### Signal History

#### Get Recent Signals

```http
GET /api/signals/history?symbol=BTCUSDT&limit=50

Response:
{
  "signals": [
    {
      "id": 1,
      "symbol": "BTCUSDT",
      "timeframe": "1h",
      "direction": "LONG",
      "confidence": 85,
      "entry_price": 45000.00,
      "created_at": "2026-05-09T10:30:00Z",
      "is_closed": false,
      "pnl_pct": null
    },
    ...
  ],
  "total": 50
}
```

#### Get Performance Statistics

```http
GET /api/signals/performance?symbol=BTCUSDT

Response:
{
  "total_trades": 45,
  "win_rate": 64.44,
  "avg_pnl": 1.23,
  "best_trade": 5.67,
  "worst_trade": -2.15,
  "winning_trades": 29,
  "losing_trades": 16
}
```

### User Preferences

#### Get User Preferences

```http
GET /api/preferences/user_123

Response:
{
  "user_id": "user_123",
  "alert_symbols": ["BTCUSDT", "ETHUSDT"],
  "alert_timeframes": ["1h", "4h"],
  "alert_min_confidence": 75,
  "preferred_timeframes": ["1h", "4h", "1d"],
  "dark_mode": true,
  "chart_type": "candlestick"
}
```

#### Update Alert Preferences

```http
POST /api/preferences/user_123/alerts?alert_symbols=BTCUSDT&alert_symbols=ETHUSDT&alert_timeframes=1h&alert_min_confidence=75

Response:
{
  "status": "updated",
  "preferences": {...}
}
```

#### Update Display Preferences

```http
POST /api/preferences/user_123/display?dark_mode=true&chart_type=candlestick

Response:
{
  "status": "updated",
  "dark_mode": true,
  "chart_type": "candlestick"
}
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

Key packages:
- `sqlalchemy==2.0.23` — ORM
- `psycopg2-binary==2.9.9` — PostgreSQL adapter
- `alembic==1.13.1` — Database migrations

### 2. Start Database Services

```bash
docker-compose up -d postgres redis
```

Verify PostgreSQL is ready:
```bash
docker-compose logs postgres | grep "database system is ready"
```

### 3. Initialize Database

```bash
cd backend
python -c "from db import init_db; init_db()"
```

This creates all tables from SQLAlchemy models.

### 4. Start Backend

```bash
# Backend starts with DB initialization
python -m uvicorn main:app --reload
```

Check `/health` endpoint:
```bash
curl http://localhost:8000/health
```

## Configuration

### Environment Variables

```bash
# Required
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=crypto_signals

# Optional
DB_POOL_SIZE=5           # Connection pool size
DB_MAX_OVERFLOW=10       # Overflow connection limit
SQL_ECHO=false           # Log all SQL queries (debug mode)
```

### Connection Pool

For serverless/Lambda:
```python
engine = create_engine(DATABASE_URL, poolclass=NullPool)
```

For traditional servers:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
)
```

## Frontend Integration

### Fetch Signal History

```javascript
// Get recent signals
const response = await fetch('/api/signals/history?limit=50')
const { signals } = await response.json()
signals.forEach(signal => {
  console.log(`${signal.symbol} ${signal.direction} @ ${signal.entry_price}`)
})

// Get stats
const stats = await fetch('/api/signals/performance').then(r => r.json())
console.log(`Win rate: ${stats.win_rate.toFixed(1)}%`)
```

### Store User Preferences

```javascript
// Update alert settings
await fetch('/api/preferences/user_123/alerts?alert_symbols=BTCUSDT&alert_min_confidence=75', {
  method: 'POST',
})

// Save to localStorage for offline access
localStorage.setItem('user_preferences', JSON.stringify(prefs))
```

## Queries & Analytics

### Get Recent Winning Signals

```sql
SELECT * FROM signals_history
WHERE is_closed = true
AND pnl_pct > 0
ORDER BY closed_at DESC
LIMIT 20;
```

### Get Win Rate by Timeframe

```sql
SELECT
  timeframe,
  COUNT(*) as total_trades,
  SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::float / COUNT(*) * 100 as win_rate
FROM signals_history
WHERE is_closed = true
GROUP BY timeframe;
```

### Get Average PnL by Direction

```sql
SELECT
  direction,
  COUNT(*) as total_trades,
  AVG(pnl_pct) as avg_pnl,
  STDDEV(pnl_pct) as volatility
FROM signals_history
WHERE is_closed = true
GROUP BY direction;
```

### Find Best Performing Symbol

```sql
SELECT
  symbol,
  COUNT(*) as total_trades,
  SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::float / COUNT(*) * 100 as win_rate,
  AVG(pnl_pct) as avg_pnl,
  MAX(pnl_pct) as best_trade,
  MIN(pnl_pct) as worst_trade
FROM signals_history
WHERE is_closed = true
GROUP BY symbol
ORDER BY win_rate DESC;
```

## Backup & Recovery

### Backup Database

```bash
# Full backup
docker-compose exec postgres pg_dump -U postgres crypto_signals > backup.sql

# Compressed backup
docker-compose exec postgres pg_dump -U postgres crypto_signals | gzip > backup.sql.gz
```

### Restore Database

```bash
# From SQL file
cat backup.sql | docker-compose exec -T postgres psql -U postgres crypto_signals

# From compressed file
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U postgres crypto_signals
```

## Monitoring

### Check Database Size

```sql
SELECT
  datname,
  pg_size_pretty(pg_database_size(datname)) as size
FROM pg_database
WHERE datname = 'crypto_signals';
```

### Monitor Table Sizes

```sql
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Check Connection Count

```sql
SELECT count(*) FROM pg_stat_activity;
```

## Troubleshooting

### Connection Refused

```
Error: could not connect to server: Connection refused
```

**Solution:** Ensure PostgreSQL is running:
```bash
docker-compose up -d postgres
docker-compose logs postgres
```

### Table Does Not Exist

```
ProgrammingError: (psycopg2.errors.UndefinedTable)
```

**Solution:** Initialize database:
```bash
python -c "from db import init_db; init_db()"
```

### Pool Exhaustion

```
QueuePool limit exceeded
```

**Solution:** Increase pool size in environment:
```bash
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

### Slow Queries

**Solution:** Add indexes:
```sql
CREATE INDEX idx_signals_symbol_time ON signals_history (symbol, created_at DESC);
CREATE INDEX idx_signals_closed ON signals_history (is_closed);
```

## Next Steps

- Phase 6: Authentication & Authorization (API keys, per-user rate limiting)
- Phase 7: Production Configuration (Docker, Nginx, env management)
- Phase 8: CI/CD (GitHub Actions, automated testing & deployment)
