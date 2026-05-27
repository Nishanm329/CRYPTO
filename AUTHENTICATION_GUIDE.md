# Authentication & Authorization Guide (Phase 6)

Comprehensive guide for API key authentication and quota management.

## Overview

```
Frontend Request
    ↓ (includes Authorization header)
API Gateway (Rate Limiting)
    ↓ (validates API key)
Authentication Layer
    ↓ (checks quota)
Quota Manager
    ↓ (increments counter)
Protected Endpoint
```

## Architecture

### Authentication Flow

1. Frontend includes API key in Authorization header: `Authorization: Bearer {api_key}`
2. Backend validates API key against allowed keys (loaded from environment)
3. Check daily quota for the user
4. If quota exceeded, return 429 (Too Many Requests)
5. If valid, increment request counter and process request
6. Update last_used timestamp for the API key

### Quota Tiers

- **Demo** (default): 100 requests/day
- **Pro**: 1,000 requests/day
- **Enterprise**: 10,000 requests/day

Tier determination is based on user_id prefix (MVP):
```python
if user_id.startswith("pro_"):
    tier = "pro"
elif user_id.startswith("enterprise_"):
    tier = "enterprise"
else:
    tier = "demo"
```

Later, query from subscription database.

## Setup

### Backend Configuration

#### Environment Variables

```bash
# .env file
API_KEYS=key1:user1,key2:user2,demo-key-public:demo-user

# Example:
API_KEYS=demo-key-public:demo-user,prod-key-abc123:acme-corp
```

#### Load Keys on Startup

The backend automatically loads API keys from environment on startup:

```python
@app.on_event("startup")
async def startup_event():
    APIKeyManager.load_keys()
```

### Frontend Configuration

#### Environment Variables

```bash
# .env.local file
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=demo-key-public
```

Or for production:

```bash
NEXT_PUBLIC_API_URL=https://api.cryptosignal.com
NEXT_PUBLIC_API_KEY=your-api-key-here
```

## API Key Management

### APIKeyManager Class

#### Load Keys

```python
from security import APIKeyManager

# Automatic on startup, or manual:
APIKeyManager.load_keys()
# Loads from API_KEYS environment variable
```

#### Verify API Key

```python
user_id = APIKeyManager.verify_api_key("demo-key-public")
# Returns: "demo-user" (or None if invalid)
```

### Quota Manager

#### Get User Tier

```python
from security import QuotaManager

tier = QuotaManager.get_tier("acme-corp")  # "demo", "pro", or "enterprise"
```

#### Get Daily Quota

```python
quota = QuotaManager.get_quota("acme-corp")
# Returns: 100 (demo), 1000 (pro), or 10000 (enterprise)
```

#### Check Quota

```python
quota_info = QuotaManager.check_quota("acme-corp")
# Returns:
# {
#   "remaining": 85,
#   "limit": 100,
#   "reset_at": "2026-05-10T10:30:00",
#   "exceeded": False
# }
```

#### Enforce Quota

```python
try:
    QuotaManager.enforce_quota("acme-corp")
except HTTPException:
    # Raised if quota exceeded (429 Too Many Requests)
```

#### Increment Quota

```python
QuotaManager.increment_quota("acme-corp")
# Called automatically for each authenticated request
```

## Protected Endpoints

These endpoints require API key authentication:

### Trading Endpoints

```http
GET /api/signal/{symbol}?timeframe=1h
Authorization: Bearer demo-key-public

GET /api/chart/{symbol}?timeframe=1h&limit=200
Authorization: Bearer demo-key-public

GET /api/signals/history?symbol=BTCUSDT&limit=50
Authorization: Bearer demo-key-public

GET /api/signals/performance?symbol=BTCUSDT
Authorization: Bearer demo-key-public
```

### User Preferences

```http
GET /api/preferences/{user_id}
Authorization: Bearer demo-key-public

POST /api/preferences/{user_id}/alerts
Authorization: Bearer demo-key-public

POST /api/preferences/{user_id}/display
Authorization: Bearer demo-key-public
```

All preference endpoints check that `current_user_id == {user_id}` (authorization check).

## Public Endpoints

These endpoints do NOT require authentication:

```http
GET /api/sentiment
GET /api/market-overview
GET /api/scan
GET /api/pairs
GET /api/tickers
GET /api/backtest/{symbol}
GET /api/backtest/combinations/{symbol}
GET /api/stream/{symbol}
GET /health
GET /metrics
POST /api/errors  (optional auth for per-user tracking)
```

## Error Responses

### 401 Unauthorized

```json
{
  "detail": "Missing Authorization header"
}
```

Header: `WWW-Authenticate: Bearer`

### 401 Unauthorized (Invalid Key)

```json
{
  "detail": "Invalid API key"
}
```

### 403 Forbidden

```json
{
  "detail": "Not authorized to view this user's preferences"
}
```

### 429 Too Many Requests

```json
{
  "detail": {
    "error": "Daily quota exceeded",
    "limit": 100,
    "reset_at": "2026-05-10T10:30:00"
  }
}
```

## Frontend Implementation

### Including API Key in Requests

The `lib/api.js` file automatically includes the API key:

```javascript
async function apiFetch(path, opts = {}) {
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${API_KEY}`,
    ...opts.headers,
  };

  return fetch(`${BASE}${path}`, { headers, ...opts });
}
```

### Handling Quota Errors

```javascript
try {
  const data = await api.signal("BTCUSDT");
} catch (error) {
  if (error.message.includes("quota")) {
    // Show message: "Daily quota exceeded. Please try again tomorrow."
  } else if (error.message.includes("API key")) {
    // Show message: "Invalid or missing API key"
  }
}
```

### Dynamic API Key Configuration

```javascript
// Get API key from environment (frontend can't access .env directly)
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "demo-key-public";

// Or from localStorage for per-user keys:
const API_KEY = localStorage.getItem("api_key") || process.env.NEXT_PUBLIC_API_KEY;
```

## Creating API Keys

### Generate Demo Key

For development, use the demo key:

```bash
API_KEYS=demo-key-public:demo-user
```

### Generate Production Key

For production, generate a strong key:

```bash
# Python
import secrets
key = secrets.token_urlsafe(32)
print(key)
# Example output: eB3n5mK9xL2qR7wU4pT6aZ8bF1gH0jS9kC5dM8nP3qR

# Bash
openssl rand -hex 32
# Example output: a7b2c9d1e5f3g8h6i2j4k1l9m0n8p7q5r2s6t8u1v3w9x
```

### Format

```bash
# Single key
API_KEYS=<key>:<user_id>

# Multiple keys
API_KEYS=<key1>:<user1>,<key2>:<user2>,<key3>:<user3>

# Example with tiers
API_KEYS=demo-key-public:demo-user,key-abc123:acme-corp,key-xyz789:startup-inc
```

User IDs starting with prefixes determine tier:

```bash
# Demo tier
API_KEYS=...,demo-key:demo-user

# Pro tier
API_KEYS=...,pro-key:pro_acme-corp

# Enterprise tier
API_KEYS=...,enterprise-key:enterprise_mega-corp
```

## Logging & Monitoring

### Log Valid Authentication

```python
logger.info(
    "API key verified for user demo-user",
    action="api_key_verified",
    user_id="demo-user",
)
```

### Log Invalid Authentication

```python
logger.warning(
    "Invalid API key attempt",
    action="invalid_api_key",
    key_hash="a7b2c9d1",  # First 8 chars of key hash
)
```

### Monitor Quota Usage

Quotas are tracked in-memory (use Redis in production):

```python
# Check quota state
quota_info = QuotaManager.check_quota("acme-corp")

# Log usage
logger.info(
    f"Quota check: {quota_info['remaining']}/{quota_info['limit']}",
    action="quota_check",
    user_id="acme-corp",
    remaining=quota_info['remaining'],
)
```

### Database Tracking

API key usage is tracked in `user_preferences` table:

```sql
SELECT user_id, api_key_last_used
FROM user_preferences
WHERE api_key_last_used IS NOT NULL
ORDER BY api_key_last_used DESC;
```

## Quota Reset

Quotas reset at UTC midnight:

```python
reset_at = quota_entry["reset_at"]
# Example: 2026-05-10T10:30:00 (UTC)

# Automatically resets when check_quota() detects reset_at < now
```

For per-user reset times, use Redis:

```python
# Set expiration on quota key
redis_client.setex(f"quota:{user_id}", 86400, count)  # 24-hour TTL
```

## Best Practices

### Security

1. **Never commit API keys** to version control
2. **Use environment variables** for sensitive values
3. **Rotate keys regularly** in production
4. **Hash keys** in logs (e.g., first 8 chars + hash)
5. **Use HTTPS** in production

### Rate Limiting Strategy

- **Per-IP**: slowapi middleware (existing)
- **Per-API-Key**: QuotaManager (new)
- **Combine both**: IP limit + quota limit provides defense-in-depth

### Monitoring

```sql
-- Check quota exceeds in last 24h
SELECT COUNT(*), user_id
FROM error_logs
WHERE error_code = 'RATE_LIMITED'
  AND created_at > now() - interval '24 hours'
GROUP BY user_id
ORDER BY COUNT(*) DESC;

-- Find most active users
SELECT user_id, api_key_last_used
FROM user_preferences
WHERE api_key_last_used > now() - interval '7 days'
ORDER BY api_key_last_used DESC;
```

## Troubleshooting

### "Missing Authorization header"

**Problem**: Frontend not sending API key

**Solution**: Verify `NEXT_PUBLIC_API_KEY` is set in `.env.local`:

```bash
NEXT_PUBLIC_API_KEY=demo-key-public
```

Then restart the dev server.

### "Invalid API key"

**Problem**: API key not in backend configuration

**Solution**: Add key to environment:

```bash
API_KEYS=demo-key-public:demo-user,<your-key>:<user>
```

Restart backend.

### "Daily quota exceeded"

**Problem**: User hit rate limit

**Solution**: 
- Check reset time: `GET /api/preferences/{user_id}` shows quota info
- Wait until reset time
- Or upgrade to Pro tier: change user_id prefix to `pro_`

### Quota Not Resetting

**Problem**: Quota resets are not working

**Solution**: QuotaManager is in-memory. Restart backend to reset all quotas:

```bash
docker-compose restart backend
```

For persistent quotas, migrate to Redis (Phase 7).

## Production Checklist

- [ ] Generate strong API keys (not demo keys)
- [ ] Store keys in secure secrets manager (AWS Secrets Manager, HashiCorp Vault)
- [ ] Rotate keys on schedule (monthly)
- [ ] Monitor quota usage in real-time
- [ ] Set up alerts for quota abuse (>95% usage)
- [ ] Use HTTPS for all API calls
- [ ] Log all authentication attempts
- [ ] Implement Redis for persistent quotas across server restarts
- [ ] Add subscription service integration for dynamic tier assignment
- [ ] Set up rate limiting dashboard

## Next Steps

- Phase 7: Production Configuration (Docker, Nginx, env management)
- Phase 8: CI/CD (GitHub Actions, automated testing & deployment)
- Phase 9: Documentation (API docs, deployment runbook)
