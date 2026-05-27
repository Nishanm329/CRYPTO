# API Reference

Complete API documentation for CryptoSignal AI backend.

## Authentication

All endpoints (except public ones) require API key authentication:

```http
Authorization: Bearer {api_key}
```

Example:
```bash
curl -H "Authorization: Bearer demo-key-public" \
  https://api.cryptosignal.com/api/signal/BTCUSDT
```

## Rate Limiting

- **Global**: 10 requests/second per IP
- **Quota**: Per-user daily quota (demo: 100, pro: 1,000, enterprise: 10,000)
- **Per-endpoint**: Specific limits for high-load endpoints

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 2026-05-10T10:30:00Z
```

## Base URL

```
https://api.cryptosignal.com
```

## Endpoints

### Trading Signals

#### Get Signal for Symbol
```http
GET /api/signal/{symbol}?timeframe=1h
Authorization: Bearer {api_key}

Query Parameters:
  symbol (string, required): Cryptocurrency pair (e.g., BTCUSDT, ETHUSDT)
  timeframe (string, optional): Candlestick timeframe (default: 1h)
    Valid: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 3d, 1w

Response: 200 OK
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "direction": "LONG",
  "entry_price": 45000.00,
  "stop_loss": 44000.00,
  "take_profits": [
    {"level": 1, "price": 46000.00, "rr_ratio": 1.0, "pct_gain": 2.22},
    {"level": 2, "price": 47500.00, "rr_ratio": 2.5, "pct_gain": 5.56}
  ],
  "confidence": 85,
  "ai_probability": 0.87,
  "rr_ratio": 2.5,
  "indicators": [
    {
      "name": "EMA 7/25 Cross",
      "value": 45000.0,
      "status": "BULLISH",
      "description": "7-EMA above 25-EMA"
    }
  ],
  "sentiment_score": 0.35,
  "volume_ratio": 1.8,
  "atr": 500.0,
  "timestamp": "2026-05-09T10:30:00Z",
  "candles_since_cross": 3,
  "position_size_1pct": 0.022
}
```

Errors:
- 400: Invalid symbol or timeframe
- 401: Missing/invalid API key
- 404: Symbol not found
- 429: Quota exceeded

---

#### Get Chart Data
```http
GET /api/chart/{symbol}?timeframe=1h&limit=200
Authorization: Bearer {api_key}

Query Parameters:
  symbol (string, required): Cryptocurrency pair
  timeframe (string, optional): Default: 1h
  limit (integer, optional): Number of candles (50-500, default: 200)

Response: 200 OK
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "bars": [
    {
      "time": 1715250600,
      "open": 44950.00,
      "high": 45100.00,
      "low": 44900.00,
      "close": 45050.00,
      "volume": 1250.5
    }
  ],
  "ema7": [
    {"time": 1715250600, "value": 45020.00}
  ],
  "ema25": [
    {"time": 1715250600, "value": 44980.00}
  ],
  "rsi": [
    {"time": 1715250600, "value": 65.5}
  ],
  "macd": [...],
  "signals": [
    {"time": 1715250600, "type": "BULLISH", "price": 45000.00}
  ],
  "latest_values": {
    "close": 45050.00,
    "rsi": 65.5,
    "ema7": 45020.00,
    "ema25": 44980.00
  }
}
```

---

### Market Scanning

#### Scan All Pairs
```http
GET /api/scan?timeframe=1h&max_pairs=50&min_confidence=50
Authorization: Bearer {api_key}

Query Parameters:
  timeframe (string, optional): Default: 1h
  max_pairs (integer, optional): Max results (default: 50)
  min_confidence (integer, optional): Min confidence 0-100 (default: 50)

Response: 200 OK
{
  "signals": [
    {
      "symbol": "BTCUSDT",
      "timeframe": "1h",
      "direction": "LONG",
      "confidence": 85,
      "ai_probability": 0.87,
      "price": 45000.00,
      "change_24h": 2.5,
      "volume_24h": 28500000000,
      "rr_ratio": 2.5,
      "timestamp": "2026-05-09T10:30:00Z"
    }
  ],
  "total_scanned": 150,
  "long_count": 12,
  "short_count": 5,
  "scan_duration_ms": 2340
}
```

---

### Backtesting

#### Backtest Strategy
```http
GET /api/backtest/{symbol}?timeframe=1h&limit=500
Authorization: Bearer {api_key}

Query Parameters:
  symbol (string, required): Trading pair
  timeframe (string, optional): Default: 1h
  limit (integer, optional): Candles to backtest (default: 500)

Response: 200 OK
{
  "strategy": "EMA Cross 7/25",
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "start_date": "2026-03-10",
  "end_date": "2026-05-09",
  "total_trades": 15,
  "win_rate": 66.67,
  "profit_factor": 2.45,
  "max_drawdown": 12.5,
  "sharpe_ratio": 1.85,
  "avg_trade_duration_hours": 8.5,
  "total_return_pct": 18.75,
  "best_trade_pct": 5.5,
  "worst_trade_pct": -3.2,
  "trades": [
    {
      "entry_time": "2026-03-10T14:00:00Z",
      "exit_time": "2026-03-11T08:00:00Z",
      "direction": "LONG",
      "entry_price": 44000.00,
      "exit_price": 44500.00,
      "pnl_pct": 1.14
    }
  ]
}
```

---

#### Backtest Combinations
```http
GET /api/backtest/combinations/{symbol}?timeframe=1d&years=6
Authorization: Bearer {api_key}

Query Parameters:
  symbol (string, required): Trading pair
  timeframe (string, optional): Default: 1d
  years (integer, optional): Historical years to test (default: 6)

Response: 200 OK
{
  "symbol": "BTCUSDT",
  "timeframe": "1d",
  "years_tested": 6,
  "start_date": "2020-05-09",
  "end_date": "2026-05-09",
  "total_bars": 1825,
  "combinations_tested": 250,
  "results": [
    {
      "rank": 1,
      "id": "combo_0001",
      "name": "EMA 7/25 + RSI(70,30)",
      "description": "EMA cross with RSI confirmation",
      "filter_count": 2,
      "filters": ["ema_cross_7_25", "rsi_confirmation"],
      "total_trades": 156,
      "win_rate": 62.8,
      "profit_factor": 2.15,
      "max_drawdown": 18.5,
      "sharpe_ratio": 1.65,
      "total_return_pct": 285.5,
      "best_trade_pct": 12.5,
      "worst_trade_pct": -5.2,
      "avg_bars": 4.8,
      "equity_curve": [100, 101.5, 102.2, ...]
    }
  ],
  "best_combination": "combo_0001",
  "best_sharpe": 1.65,
  "generated_at": "2026-05-09T10:30:00Z"
}
```

---

### Market Data

#### Get Market Sentiment
```http
GET /api/sentiment

Response: 200 OK
{
  "fear_greed": {
    "value": 72,
    "classification": "Greed",
    "timestamp": "2026-05-09T10:00:00Z"
  },
  "overall_score": 0.44,
  "classification": "Bullish",
  "positive_pct": 72,
  "negative_pct": 15,
  "neutral_pct": 13,
  "components": {
    "fear_greed_index": 72,
    "market_dominance": 0.52,
    "volume_trend": 1.2
  }
}
```

---

#### Get Top Trading Pairs
```http
GET /api/tickers?symbols=BTCUSDT,ETHUSDT

Query Parameters:
  symbols (string, optional): Comma-separated symbols

Response: 200 OK
{
  "tickers": [
    {
      "symbol": "BTCUSDT",
      "price": 45000.00,
      "change_24h": 2.5,
      "change_pct_24h": 5.87,
      "high_24h": 45500.00,
      "low_24h": 43500.00,
      "volume_24h": 28500000000,
      "volume_usd_24h": 28500000000
    }
  ]
}
```

---

#### Get Market Overview
```http
GET /api/market-overview

Response: 200 OK
{
  "total_market_cap": 1850000000000,
  "total_volume_24h": 85000000000,
  "btc_dominance": 45.5,
  "fear_greed_index": 72,
  "top_gainers": [
    {"symbol": "ETHUSDT", "change_pct_24h": 8.5, "price": 2800.00}
  ],
  "top_losers": [
    {"symbol": "ADAUSDT", "change_pct_24h": -3.2, "price": 0.95}
  ]
}
```

---

#### Get Available Pairs
```http
GET /api/pairs

Response: 200 OK
{
  "pairs": [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "ADAUSDT",
    ...
  ],
  "total": 150
}
```

---

### Signal History & Preferences

#### Get Signal History
```http
GET /api/signals/history?symbol=BTCUSDT&limit=50
Authorization: Bearer {api_key}

Query Parameters:
  symbol (string, optional): Filter by symbol
  limit (integer, optional): Max results (default: 50)

Response: 200 OK
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
    }
  ],
  "total": 45
}
```

---

#### Get Performance Statistics
```http
GET /api/signals/performance?symbol=BTCUSDT
Authorization: Bearer {api_key}

Query Parameters:
  symbol (string, optional): Filter by symbol

Response: 200 OK
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

---

### User Preferences

#### Get User Preferences
```http
GET /api/preferences/{user_id}
Authorization: Bearer {api_key}

Response: 200 OK
{
  "user_id": "demo-user",
  "alert_symbols": ["BTCUSDT", "ETHUSDT"],
  "alert_timeframes": ["1h", "4h"],
  "alert_min_confidence": 75,
  "preferred_timeframes": ["1h", "4h", "1d"],
  "dark_mode": true,
  "chart_type": "candlestick"
}
```

---

#### Update Alert Preferences
```http
POST /api/preferences/{user_id}/alerts?alert_symbols=BTCUSDT&alert_min_confidence=80
Authorization: Bearer {api_key}

Query Parameters:
  alert_symbols (string, optional): Comma-separated symbols
  alert_timeframes (string, optional): Comma-separated timeframes
  alert_min_confidence (integer, optional): Min confidence 0-100

Response: 200 OK
{
  "status": "updated",
  "preferences": {...}
}
```

---

#### Update Display Preferences
```http
POST /api/preferences/{user_id}/display?dark_mode=true&chart_type=candlestick
Authorization: Bearer {api_key}

Query Parameters:
  dark_mode (boolean, optional): Dark mode enabled
  chart_type (string, optional): Chart type

Response: 200 OK
{
  "status": "updated",
  "dark_mode": true,
  "chart_type": "candlestick"
}
```

---

### Server Status

#### Health Check
```http
GET /health

Response: 200 OK
{
  "status": "ok",
  "timestamp": "2026-05-09T10:30:00Z"
}
```

---

#### Get Metrics (Prometheus)
```http
GET /metrics

Response: 200 OK
# HELP requests_total Total requests
# TYPE requests_total counter
requests_total{method="GET",path="/api/signal",status="200"} 1250.0

# HELP request_duration_seconds Request duration
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{method="GET",le="0.1"} 1200.0
request_duration_seconds_bucket{method="GET",le="0.5"} 1245.0
...
```

---

#### Log Frontend Errors
```http
POST /api/errors

Body:
{
  "message": "Failed to fetch chart data",
  "type": "NetworkError",
  "url": "https://cryptosignal.com/dashboard",
  "stack": "Error: Network request failed\n  at Chart.tsx:45"
}

Response: 200 OK
{
  "status": "logged",
  "request_id": "req-abc123def456"
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message or object"
}
```

### Common Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 401 | Unauthorized (missing/invalid API key) |
| 403 | Forbidden (no permission) |
| 404 | Not found |
| 429 | Too many requests (quota exceeded) |
| 500 | Server error |

### Error Examples

**401 Unauthorized**
```json
{
  "detail": "Invalid API key"
}
```

**429 Too Many Requests**
```json
{
  "detail": {
    "error": "Daily quota exceeded",
    "limit": 100,
    "reset_at": "2026-05-10T10:30:00Z"
  }
}
```

**400 Bad Request**
```json
{
  "detail": "Invalid symbol: INVALID-SYMBOL"
}
```

---

## WebSocket Endpoints

### Live Price Stream
```
WS /api/stream/{symbol}?timeframe=1h

Message (every 10 seconds):
{
  "symbol": "BTCUSDT",
  "price": 45000.00,
  "open": 44950.00,
  "high": 45100.00,
  "low": 44900.00,
  "volume": 1250.5,
  "rsi": 65.5,
  "ema7": 45020.00,
  "ema25": 44980.00,
  "timestamp": "2026-05-09T10:30:00Z"
}
```

---

## Response Headers

All responses include:

```
Content-Type: application/json
X-Request-ID: {unique-request-id}
X-RateLimit-Limit: {quota-limit}
X-RateLimit-Remaining: {remaining-requests}
X-RateLimit-Reset: {reset-timestamp}
```

---

## Code Examples

### Python
```python
import requests

headers = {"Authorization": "Bearer demo-key-public"}

# Get signal
response = requests.get(
    "https://api.cryptosignal.com/api/signal/BTCUSDT",
    headers=headers
)
signal = response.json()
print(f"{signal['symbol']} {signal['direction']} @ {signal['entry_price']}")

# Get chart
response = requests.get(
    "https://api.cryptosignal.com/api/chart/BTCUSDT?limit=200",
    headers=headers
)
chart = response.json()
print(f"Loaded {len(chart['bars'])} candles")
```

### JavaScript
```javascript
const API_KEY = "demo-key-public";
const BASE_URL = "https://api.cryptosignal.com";

async function getSignal(symbol) {
  const response = await fetch(
    `${BASE_URL}/api/signal/${symbol}`,
    {
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
        "Content-Type": "application/json"
      }
    }
  );
  return response.json();
}

const signal = await getSignal("BTCUSDT");
console.log(`${signal.symbol} ${signal.direction} @ ${signal.entry_price}`);
```

### cURL
```bash
# Get signal
curl -H "Authorization: Bearer demo-key-public" \
  https://api.cryptosignal.com/api/signal/BTCUSDT

# Get chart
curl -H "Authorization: Bearer demo-key-public" \
  "https://api.cryptosignal.com/api/chart/BTCUSDT?limit=200"

# Scan market
curl -H "Authorization: Bearer demo-key-public" \
  "https://api.cryptosignal.com/api/scan?max_pairs=50&min_confidence=70"
```

---

## Rate Limit Examples

### Check Rate Limit

```bash
curl -H "Authorization: Bearer demo-key-public" \
  -i https://api.cryptosignal.com/api/signal/BTCUSDT

# Response headers:
# X-RateLimit-Limit: 100
# X-RateLimit-Remaining: 45
# X-RateLimit-Reset: 2026-05-10T10:30:00Z
```

### Handle 429 Response

```javascript
async function apiCall(endpoint) {
  const response = await fetch(endpoint, {
    headers: { "Authorization": `Bearer ${API_KEY}` }
  });

  if (response.status === 429) {
    const resetTime = response.headers.get("X-RateLimit-Reset");
    throw new Error(`Quota exceeded. Reset at ${resetTime}`);
  }

  return response.json();
}
```

---

## OpenAPI Schema

Interactive API documentation available at:

```
https://api.cryptosignal.com/docs        (Swagger UI)
https://api.cryptosignal.com/redoc       (ReDoc)
https://api.cryptosignal.com/openapi.json (OpenAPI JSON)
```

---

## Support

For API support:
- GitHub Issues: https://github.com/your-org/crypto-signals/issues
- Email: support@cryptosignal.com
- Slack: https://cryptosignal.slack.com
