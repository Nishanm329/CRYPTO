# Production Deployment Guide

Comprehensive guide for deploying CryptoSignal AI to production environments.

## Prerequisites

- Docker and Docker Compose (version 20.10+)
- Domain name (e.g., cryptosignal.com)
- SSL certificates (Let's Encrypt recommended)
- Server with 4+ CPU cores and 8GB+ RAM
- Reverse proxy (Nginx) configured
- PostgreSQL database (production instance)
- Redis cache (production instance, optional)

## Pre-Deployment Checklist

### 1. Environment Configuration

```bash
# Copy production environment file
cp .env.production.example .env.production

# Edit with production values
vim .env.production

# CRITICAL: Change all default passwords
# - DB_PASSWORD
# - REDIS_PASSWORD

# Add production API keys
API_KEYS=your-key-1:user1,your-key-2:user2

# Set CORS for production domain
CORS_ORIGINS=https://cryptosignal.com,https://app.cryptosignal.com

# Set Sentry DSN for error tracking
SENTRY_DSN=https://xxx@sentry.io/yyy
```

### 2. SSL Certificates

Generate with Let's Encrypt:

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificates
sudo certbot certonly --standalone \
  -d cryptosignal.com \
  -d api.cryptosignal.com \
  -d app.cryptosignal.com

# Copy to project directory
mkdir -p ssl/certs
sudo cp /etc/letsencrypt/live/cryptosignal.com/fullchain.pem ssl/certs/
sudo cp /etc/letsencrypt/live/cryptosignal.com/privkey.pem ssl/certs/
sudo cp /etc/ssl/dhparam.pem ssl/  # or generate: openssl dhparam -out ssl/dhparam.pem 2048

# Fix permissions
chmod 644 ssl/certs/*
chmod 644 ssl/dhparam.pem
```

Or use your own CA certificates:

```bash
mkdir -p ssl/certs
cp /path/to/fullchain.pem ssl/certs/
cp /path/to/privkey.pem ssl/certs/
cp /path/to/dhparam.pem ssl/
```

### 3. Database Preparation

If using external PostgreSQL (AWS RDS, etc.):

```bash
# Test connection
psql -h your-rds-endpoint.amazonaws.com \
     -U postgres \
     -d postgres \
     -c "SELECT version();"

# Initialize database
psql -h your-rds-endpoint.amazonaws.com \
     -U postgres \
     -d postgres \
     -f scripts/init-db.sql
```

Or use Docker services from docker-compose.prod.yml:

```bash
# Will automatically initialize on first run
```

### 4. Secrets Management

For production, use a secrets manager:

**AWS Secrets Manager:**
```bash
aws secretsmanager create-secret \
  --name crypto-signals/prod \
  --secret-string file://secrets.json
```

**HashiCorp Vault:**
```bash
vault kv put secret/crypto-signals/prod \
  db_password=xxx \
  api_keys=xxx
```

**Docker Secrets (Swarm):**
```bash
docker secret create db_password -
# Then reference in compose: file: db_password
```

## Deployment Steps

### Option 1: Docker Compose (Single Server)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/crypto-signals.git
cd crypto-signals

# 2. Set up environment
cp .env.production.example .env.production
vim .env.production  # Edit with production values

# 3. Create SSL directory
mkdir -p ssl/certs
# Copy certificates (see SSL section above)

# 4. Pull latest images
docker-compose -f docker-compose.prod.yml pull

# 5. Start services
docker-compose -f docker-compose.prod.yml up -d

# 6. Verify services are running
docker-compose -f docker-compose.prod.yml ps

# 7. Check logs
docker-compose -f docker-compose.prod.yml logs -f backend

# 8. Test health endpoint
curl https://cryptosignal.com/health
```

### Option 2: Docker Swarm (High Availability)

```bash
# 1. Initialize swarm
docker swarm init

# 2. Create secrets
echo "production-password" | docker secret create db_password -
echo "key1:user1,key2:user2" | docker secret create api_keys -

# 3. Deploy stack
docker stack deploy -c docker-compose.prod.yml crypto-signals

# 4. Check deployment
docker stack ps crypto-signals

# 5. View logs
docker service logs crypto-signals_backend
```

### Option 3: Kubernetes (Enterprise)

```bash
# 1. Create namespace
kubectl create namespace crypto-signals

# 2. Create secrets
kubectl create secret generic db-credentials \
  --from-literal=DB_PASSWORD=xxx \
  --from-literal=REDIS_PASSWORD=xxx \
  -n crypto-signals

# 3. Create ConfigMap for non-sensitive config
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=INFO \
  --from-literal=ENVIRONMENT=production \
  -n crypto-signals

# 4. Deploy Helm chart (if available)
helm install crypto-signals ./helm-charts/crypto-signals \
  -n crypto-signals \
  -f values-prod.yaml

# 5. Verify deployment
kubectl get pods -n crypto-signals
kubectl describe pod <pod-name> -n crypto-signals
```

## Post-Deployment Verification

### 1. Health Checks

```bash
# Backend health
curl https://cryptosignal.com/health
# Expected: {"status": "ok", "timestamp": "..."}

# Frontend accessibility
curl https://cryptosignal.com/
# Expected: HTML content

# API authentication
curl -H "Authorization: Bearer your-api-key" \
  https://api.cryptosignal.com/api/signal/BTCUSDT
```

### 2. Database Verification

```bash
# Connect to database
psql -h your-db-host -U postgres -d crypto_signals

# Check tables
\dt

# Verify signal history table
SELECT COUNT(*) FROM signals_history;
```

### 3. Service Status

```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# Check service logs
docker-compose -f docker-compose.prod.yml logs backend
docker-compose -f docker-compose.prod.yml logs frontend
docker-compose -f docker-compose.prod.yml logs nginx

# Check Nginx status
curl -I https://cryptosignal.com/health
```

### 4. Monitoring Setup

```bash
# View Prometheus metrics
curl https://cryptosignal.com:9090/metrics

# Set up Grafana dashboard
# - Add Prometheus as data source
# - Import dashboard from ./monitoring/grafana-dashboard.json

# Enable Sentry error tracking
# - Verify SENTRY_DSN is set
# - Test error logging: curl -X POST \
#   https://api.cryptosignal.com/api/errors \
#   -H "Content-Type: application/json" \
#   -d '{"message":"test error"}'
```

## Configuration Updates

### Updating Environment Variables

```bash
# 1. Update .env.production
vim .env.production

# 2. Restart services
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# OR for zero-downtime (if using multiple replicas):
docker service update --env-add NEW_VAR=value crypto-signals_backend
```

### Database Migrations

```bash
# 1. Run migrations in container
docker-compose -f docker-compose.prod.yml exec backend \
  alembic upgrade head

# 2. Verify migrations
docker-compose -f docker-compose.prod.yml exec backend \
  alembic current

# 3. Check database schema
docker-compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres -d crypto_signals -c "\dt"
```

## Scaling

### Horizontal Scaling (Multiple Containers)

```bash
# Scale backend service
docker-compose -f docker-compose.prod.yml up -d --scale backend=3

# Or with Docker Swarm
docker service scale crypto-signals_backend=3

# Or with Kubernetes
kubectl scale deployment backend --replicas=3 -n crypto-signals
```

### Load Balancing

Nginx automatically load-balances across multiple backend instances:

```nginx
upstream backend {
    server backend:8000;
    server backend:8001;
    server backend:8002;
}
```

## Monitoring & Logging

### Log Aggregation

```bash
# View logs in real-time
docker-compose -f docker-compose.prod.yml logs -f backend

# Export logs to file
docker-compose -f docker-compose.prod.yml logs backend > logs.txt

# Use ELK Stack for centralized logging
# - Filebeat ships logs to Elasticsearch
# - Kibana visualizes in dashboards
```

### Metrics & Alerts

```bash
# Prometheus scrapes metrics from /metrics
# Configure alerts in Prometheus:
groups:
  - name: crypto-signals
    rules:
      - alert: HighErrorRate
        expr: rate(requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"

# Alertmanager sends notifications:
# - Email
# - PagerDuty
# - Slack
```

## Backup & Recovery

### Automated Backups

```bash
# Daily backup script
0 2 * * * /backup-database.sh

# Script content:
#!/bin/bash
pg_dump -h postgres -U postgres crypto_signals | \
  gzip > /backups/db-$(date +%Y%m%d).sql.gz

# Upload to S3
aws s3 cp /backups/db-*.sql.gz s3://my-backup-bucket/
```

### Manual Backup

```bash
# Full database backup
docker-compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres crypto_signals | gzip > backup.sql.gz

# Restore from backup
gunzip -c backup.sql.gz | \
  docker-compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres crypto_signals
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs

# Common issues:
# - Port already in use: lsof -i :8000
# - Database not accessible: docker-compose exec postgres psql...
# - Certificate issues: openssl x509 -in ssl/certs/fullchain.pem -text
```

### Database Connection Errors

```bash
# Test database connectivity
docker-compose -f docker-compose.prod.yml exec backend \
  psql -h postgres -U postgres -d crypto_signals -c "SELECT 1"

# Check database logs
docker-compose -f docker-compose.prod.yml logs postgres
```

### High Memory Usage

```bash
# Check service memory
docker stats

# Adjust in docker-compose.prod.yml:
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

### SSL Certificate Expiration

```bash
# Check certificate expiration
openssl x509 -in ssl/certs/fullchain.pem -noout -dates

# Renew with certbot
sudo certbot renew --force-renewal

# Copy new certificates
sudo cp /etc/letsencrypt/live/cryptosignal.com/*.pem ssl/certs/
chmod 644 ssl/certs/*

# Reload Nginx
docker-compose -f docker-compose.prod.yml exec nginx \
  nginx -s reload
```

## Security Best Practices

✅ Use HTTPS (SSL/TLS) for all traffic
✅ Change default passwords
✅ Use environment variables for secrets
✅ Enable API key authentication
✅ Set up rate limiting
✅ Configure CORS for your domain
✅ Enable security headers (HSTS, CSP, X-Frame-Options)
✅ Keep Docker images updated
✅ Monitor logs for suspicious activity
✅ Use a secrets manager (AWS Secrets Manager, Vault)
✅ Enable database encryption at rest
✅ Set up automated backups
✅ Implement monitoring and alerting

## Production Runbook

### Daily Checks

- [ ] Verify all services are running
- [ ] Check error logs for issues
- [ ] Monitor API latency and error rate
- [ ] Verify backups completed successfully

### Weekly Checks

- [ ] Review security logs
- [ ] Check certificate expiration dates
- [ ] Review and optimize database queries
- [ ] Test disaster recovery procedures

### Monthly Checks

- [ ] Update Docker images
- [ ] Review and update API keys if needed
- [ ] Perform database maintenance
- [ ] Review monitoring and alerting rules

## Support & Rollback

### Rollback to Previous Version

```bash
# 1. Save current state
docker-compose -f docker-compose.prod.yml down

# 2. Checkout previous version
git checkout v1.x.x  # Previous version tag

# 3. Start services
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify
curl https://cryptosignal.com/health
```

### Incident Response

```bash
# 1. Check what's happening
docker-compose -f docker-compose.prod.yml logs backend

# 2. If critical, scale down
docker-compose -f docker-compose.prod.yml down

# 3. Investigate logs and metrics
# 4. Fix issue (code update, config change, etc.)
# 5. Restart services
docker-compose -f docker-compose.prod.yml up -d

# 6. Monitor closely
docker-compose -f docker-compose.prod.yml logs -f
```

## Next Steps

- Phase 8: CI/CD (GitHub Actions, automated testing & deployment)
- Phase 9: Documentation (API docs, developer guide)
