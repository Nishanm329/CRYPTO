# Production Configuration Guide

Detailed guide for configuring CryptoSignal AI for production deployment.

## Configuration Hierarchy

```
1. Environment Variables (.env.production)
   └─ Loaded by config.py
   └─ Overrides defaults
   └─ Used in docker-compose.prod.yml
```

## Configuration File Structure

### Backend Configuration (config.py)

```python
class Config:
    ENV = os.getenv("ENVIRONMENT", "development")
    DEBUG = ENV == "development"
    
    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "crypto_signals")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Monitoring
    PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true")
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")
    
    # Rate Limiting
    RATE_LIMIT_SIGNAL = int(os.getenv("RATE_LIMIT_SIGNAL", "60"))
```

### Frontend Configuration (.env.local or .env.production)

```javascript
process.env.NEXT_PUBLIC_API_URL
process.env.NEXT_PUBLIC_API_KEY
process.env.NEXT_PUBLIC_SENTRY_DSN
```

## Required Configuration

### Minimum Production Setup

```bash
# .env.production (REQUIRED fields)
ENVIRONMENT=production
DB_HOST=your-database-host
DB_USER=postgres
DB_PASSWORD=secure-password  # Change this!
DB_NAME=crypto_signals
SENTRY_DSN=https://xxx@sentry.io/yyy
API_KEYS=your-production-key:company-name
CORS_ORIGINS=https://yourdomain.com
```

### Full Production Setup

```bash
# Backend (.env.production)
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Database
DB_HOST=your-rds.amazonaws.com
DB_USER=postgres
DB_PASSWORD=${DB_PASSWORD}  # From secrets manager
DB_PORT=5432
DB_NAME=crypto_signals
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://redis.elasticache.amazonaws.com:6379
REDIS_PASSWORD=${REDIS_PASSWORD}  # From secrets manager

# Logging
LOG_LEVEL=INFO

# External APIs
BINANCE_API_KEY=${BINANCE_API_KEY}
BINANCE_API_SECRET=${BINANCE_API_SECRET}
FEAR_GREED_API_KEY=${FEAR_GREED_API_KEY}

# Monitoring
PROMETHEUS_ENABLED=true
SENTRY_DSN=https://xxx@sentry.io/yyy

# API Keys
API_KEYS=prod-key-1:company-a,prod-key-2:company-b

# CORS
CORS_ORIGINS=https://cryptosignal.com,https://app.cryptosignal.com

# Rate Limiting
RATE_LIMIT_SIGNAL=100
RATE_LIMIT_CHART=100
RATE_LIMIT_SCAN=50
RATE_LIMIT_MARKET=30

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60

# Frontend (.env.production)
NEXT_PUBLIC_API_URL=https://api.cryptosignal.com
NEXT_PUBLIC_API_KEY=prod-key-1
NEXT_PUBLIC_SENTRY_DSN=https://xxx@sentry.io/yyy
```

## Environment-Specific Configuration

### Development Environment

```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
DB_HOST=localhost
API_KEYS=demo-key-public:demo-user
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Staging Environment

```bash
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
DB_HOST=staging-db.internal
API_KEYS=staging-key-1:company-a
CORS_ORIGINS=https://staging.cryptosignal.com
SENTRY_DSN=https://staging-dsn@sentry.io/project
```

### Production Environment

```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
DB_HOST=prod-db.amazonaws.com
API_KEYS=prod-key-1:company-a,prod-key-2:company-b
CORS_ORIGINS=https://cryptosignal.com,https://app.cryptosignal.com
SENTRY_DSN=https://prod-dsn@sentry.io/project
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
```

## Database Configuration

### Local Development

```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=crypto_signals
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
```

### AWS RDS

```bash
DB_HOST=my-db.xxxxx.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_USER=admin
DB_PASSWORD=${STORED_IN_SECRETS_MANAGER}
DB_NAME=crypto_signals
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

### GCP Cloud SQL

```bash
DB_HOST=/cloudsql/project:region:instance
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=${STORED_IN_SECRET_MANAGER}
DB_NAME=crypto_signals
```

### Azure Database for PostgreSQL

```bash
DB_HOST=my-server.postgres.database.azure.com
DB_PORT=5432
DB_USER=admin@my-server
DB_PASSWORD=${STORED_IN_VAULT}
DB_NAME=crypto_signals
```

## Redis Configuration

### Local Development

```bash
REDIS_URL=redis://localhost:6379
```

### Production (AWS ElastiCache)

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@my-redis.xxxxx.ng.0001.use1.cache.amazonaws.com:6379
```

### Production (Azure Cache for Redis)

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@my-redis.redis.cache.windows.net:6379
```

## Logging Configuration

### Development

```bash
LOG_LEVEL=DEBUG
```

### Production

```bash
LOG_LEVEL=INFO
```

### Log Aggregation (ELK Stack)

```bash
LOG_LEVEL=INFO
ELASTICSEARCH_HOST=elasticsearch.internal
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_INDEX=crypto-signals
```

## Monitoring Configuration

### Sentry Error Tracking

```bash
# Development (Optional)
SENTRY_DSN=

# Production (REQUIRED)
SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=v2.0.0
```

### Prometheus Metrics

```bash
PROMETHEUS_ENABLED=true
# Metrics available at /metrics
# Scrape interval: 15s (configure in prometheus.yml)
```

## API Key Management

### Generate Production Keys

```bash
# Python
import secrets
key = secrets.token_urlsafe(32)
print(f"{key}:company-name")

# Bash
openssl rand -hex 32 | xargs -I {} echo "{}:company-name"
```

### Key Format

```bash
API_KEYS=key1:user1,key2:user2,key3:user3
```

### Key Rotation

```bash
# 1. Generate new key
NEW_KEY=`openssl rand -hex 32`

# 2. Add to API_KEYS (keep old key for backward compatibility)
API_KEYS=old-key:user1,${NEW_KEY}:user1,other-key:user2

# 3. Notify users to update their clients

# 4. After grace period, remove old key
API_KEYS=${NEW_KEY}:user1,other-key:user2
```

## CORS Configuration

### Development

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Production - Single Domain

```bash
CORS_ORIGINS=https://cryptosignal.com
```

### Production - Multiple Domains

```bash
CORS_ORIGINS=https://cryptosignal.com,https://app.cryptosignal.com,https://api.cryptosignal.com
```

### Production - Wildcard (Not Recommended)

```bash
CORS_ORIGINS=https://*.cryptosignal.com
```

## Rate Limiting Configuration

Default rates (requests per minute):

```bash
RATE_LIMIT_SIGNAL=60        # /api/signal
RATE_LIMIT_CHART=60         # /api/chart
RATE_LIMIT_SCAN=30          # /api/scan
RATE_LIMIT_MARKET=20        # /api/market-overview
```

Increase for production with more traffic:

```bash
RATE_LIMIT_SIGNAL=300
RATE_LIMIT_CHART=300
RATE_LIMIT_SCAN=150
RATE_LIMIT_MARKET=100
```

## Circuit Breaker Configuration

```bash
# Number of failures before opening circuit
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5

# Time (seconds) before attempting to reset
CIRCUIT_BREAKER_TIMEOUT=60
```

Adjust for reliability:

```bash
# Strict (low tolerance for failures)
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_TIMEOUT=30

# Relaxed (high tolerance)
CIRCUIT_BREAKER_FAILURE_THRESHOLD=10
CIRCUIT_BREAKER_TIMEOUT=120
```

## SSL/TLS Configuration

### Let's Encrypt (Recommended)

```bash
# In docker-compose.prod.yml
ssl_certificate /etc/nginx/certs/fullchain.pem
ssl_certificate_key /etc/nginx/certs/privkey.pem

# Generate
certbot certonly --standalone -d cryptosignal.com -d api.cryptosignal.com

# Copy to ssl/certs/
```

### Custom Certificate

```bash
# Place in ssl/certs/
# - fullchain.pem (cert + chain)
# - privkey.pem (private key)
# - dhparam.pem (Diffie-Hellman parameters)

# Generate DH params
openssl dhparam -out ssl/dhparam.pem 2048
```

## Configuration Validation

The application validates critical configuration on startup:

```python
config.validate()  # Called in main.py @startup event

# Validates:
# - Database host is set
# - Database name is set
# - Production requires Sentry DSN
# - Production requires proper CORS_ORIGINS
```

## Secrets Management

### AWS Secrets Manager

```bash
# Store secrets
aws secretsmanager create-secret \
  --name crypto-signals/prod \
  --secret-string '{
    "DB_PASSWORD": "xxx",
    "REDIS_PASSWORD": "yyy",
    "API_KEYS": "key1:user1"
  }'

# Retrieve in app
import boto3
client = boto3.client('secretsmanager')
response = client.get_secret_value(SecretId='crypto-signals/prod')
secrets = json.loads(response['SecretString'])
os.environ['DB_PASSWORD'] = secrets['DB_PASSWORD']
```

### HashiCorp Vault

```bash
# Store secrets
vault kv put secret/crypto-signals/prod \
  DB_PASSWORD=xxx \
  REDIS_PASSWORD=yyy

# Retrieve in app
import hvac
client = hvac.Client(url='https://vault.internal:8200')
secrets = client.secrets.kv.read_secret_version(path='crypto-signals/prod')
os.environ.update(secrets['data']['data'])
```

## Configuration Validation Checklist

- [ ] ENVIRONMENT=production
- [ ] DATABASE credentials set (no defaults)
- [ ] API_KEYS configured (not demo keys)
- [ ] CORS_ORIGINS set to your domain
- [ ] SENTRY_DSN configured
- [ ] SSL certificates in place
- [ ] REDIS configured for production
- [ ] LOG_LEVEL set appropriately
- [ ] External API keys configured
- [ ] Rate limits adjusted for expected traffic

## Troubleshooting Configuration Issues

### "Configuration validation failed"

Check logs:
```bash
docker-compose -f docker-compose.prod.yml logs backend | grep -i config
```

Common issues:
- Missing SENTRY_DSN in production
- CORS_ORIGINS not configured
- Database credentials not set

### "Cannot connect to database"

Verify configuration:
```bash
docker-compose -f docker-compose.prod.yml exec backend \
  python -c "from config import config; print(config.DATABASE_URL)"

# Test connection
psql $(config.DATABASE_URL)
```

### "Invalid API key format"

Check API_KEYS format:
```bash
# Correct
API_KEYS=key1:user1,key2:user2

# Incorrect
API_KEYS=key1
API_KEYS=key1:user1:extra

# Fix
API_KEYS=your-key:your-user
```

## Performance Tuning

### Database Connection Pool

For high traffic, increase pool size:

```bash
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=60
```

### Worker Processes

For multi-core servers:

```bash
WORKERS=8  # Number of CPU cores
```

### Rate Limiting

For high-volume APIs, increase limits:

```bash
RATE_LIMIT_SIGNAL=500
RATE_LIMIT_CHART=500
RATE_LIMIT_SCAN=200
```

## Next Steps

- Phase 8: CI/CD (GitHub Actions for automated deployment)
- Phase 9: Documentation (API reference, developer guide)
