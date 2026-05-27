# Auto-Execution Feature - Deployment Guide

## 📋 Pre-Deployment Checklist

```
[ ] All tests passing locally (44/44)
[ ] Code reviewed and approved
[ ] Database migration script tested
[ ] Environment variables configured
[ ] SSL certificates ready (if using HTTPS)
[ ] Backups created
[ ] Team notified
[ ] Monitoring configured
[ ] Rollback plan documented
```

---

## 🚀 Deployment Overview

The auto-execution feature deployment follows a **3-stage rollout**:

1. **Development** → Local testing with SQLite
2. **Staging** → Full cloud deployment with PostgreSQL
3. **Production** → Full production deployment with monitoring

---

## Stage 1: Development (Local)

### Prerequisites
```bash
# Python 3.9+
python3 --version

# Node.js 18+
node --version
npm --version

# SQLite3 (included with Python)
```

### Setup
```bash
# 1. Clone repository
git clone <your-repo>
cd crypto-signals

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install backend dependencies
cd backend
pip install -r requirements.txt
pip install -e .

# 4. Initialize database
python3 -c "from db import init_db; init_db()"

# 5. Run tests
pytest tests/test_auto_execution_engine.py -v --cov=auto_execution_engine
# Expected: 44 passed, 100% coverage

# 6. Start backend
python3 -m uvicorn main:app --reload --port 8000

# 7. In new terminal, setup frontend
cd frontend
npm install
npm run dev
# Frontend runs on http://localhost:3000
```

### Verify Development Deployment
```bash
# Test signal endpoint
curl -H "Authorization: Bearer test-key" \
  http://localhost:8000/api/signal/BTCUSDT

# Test auto-execution settings
curl -X GET \
  -H "Authorization: Bearer test-key" \
  http://localhost:8000/api/trading/auto-execution/status
```

---

## Stage 2: Staging (Cloud)

### Prerequisites
```bash
# Docker & Docker Compose
docker --version
docker-compose --version

# Cloud CLI tools (choose one)
aws --version          # For AWS
gcloud --version       # For GCP
vercel --version       # For Vercel
```

### Environment Setup

**1. Create .env.staging file**
```bash
cp .env.example .env.staging
```

**Edit .env.staging:**
```
ENVIRONMENT=staging
DATABASE_URL=postgresql://user:pass@staging-db.example.com:5432/crypto_signals_staging
REDIS_URL=redis://:pass@staging-redis.example.com:6379/0
NEXT_PUBLIC_API_URL=https://staging-api.cryptosignal.app
```

**2. Create docker-compose.staging.yml**
```bash
cp docker-compose.prod.yml docker-compose.staging.yml
```

Edit for staging (use staging database, etc.)

### Deployment Steps

**Option A: AWS ECS**
```bash
# 1. Build Docker images
docker-compose -f docker-compose.staging.yml build

# 2. Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URL
docker tag crypto-signals-backend:latest YOUR_ECR_URL/crypto-signals-backend:staging
docker push YOUR_ECR_URL/crypto-signals-backend:staging

# 3. Update ECS service
aws ecs update-service \
  --cluster crypto-signals-staging \
  --service crypto-signals-backend \
  --force-new-deployment

# 4. Monitor deployment
aws ecs describe-services \
  --cluster crypto-signals-staging \
  --services crypto-signals-backend
```

**Option B: Docker Compose (VPS/Dedicated Server)**
```bash
# 1. SSH into staging server
ssh staging@staging-server.com

# 2. Pull latest code
cd /app/crypto-signals
git pull origin staging

# 3. Start services
docker-compose -f docker-compose.staging.yml down
docker-compose -f docker-compose.staging.yml up -d

# 4. Run migrations
docker-compose -f docker-compose.staging.yml exec backend \
  python3 -c "from db import init_db; init_db()"

# 5. Check logs
docker-compose -f docker-compose.staging.yml logs -f backend
```

**Option C: Vercel (Frontend) + Cloud Run (Backend)**
```bash
# Backend: Deploy to Google Cloud Run
gcloud run deploy crypto-signals-backend \
  --source backend \
  --platform managed \
  --region us-central1 \
  --set-env-vars DATABASE_URL=<staging-db-url>

# Frontend: Deploy to Vercel
cd frontend
vercel --prod --env staging
```

### Verify Staging Deployment
```bash
# 1. Health check
curl https://staging-api.cryptosignal.app/health

# 2. Test signal endpoint
curl -H "Authorization: Bearer test-key" \
  https://staging-api.cryptosignal.app/api/signal/BTCUSDT

# 3. Test auto-execution endpoints
curl -H "Authorization: Bearer test-key" \
  https://staging-api.cryptosignal.app/api/trading/auto-execution/status

# 4. Check logs
# AWS: CloudWatch Logs
# GCP: Cloud Logging
# VPS: docker logs

# 5. Run smoke tests
cd tests
pytest tests/test_api_integration.py -v --staging
```

### 24-Hour Staging Validation
```
Day 1: Monitor these metrics
[ ] API response times < 500ms
[ ] Zero database connection errors
[ ] Auto-execution audit logs flowing
[ ] No memory leaks (check container memory)
[ ] All external API calls succeeding
[ ] Rate limiting working correctly
```

---

## Stage 3: Production (Cloud)

### Pre-Production Checklist
```
[ ] Staging deployment stable for 24+ hours
[ ] Security audit completed
[ ] Database backups scheduled
[ ] Monitoring and alerting configured
[ ] Rollback procedures documented and tested
[ ] Team training completed
[ ] Stakeholder approval obtained
```

### Production Deployment

**Step 1: Database Backup**
```bash
# AWS RDS
aws rds create-db-snapshot \
  --db-instance-identifier crypto-signals-prod \
  --db-snapshot-identifier crypto-signals-prod-pre-autofx-backup

# GCP Cloud SQL
gcloud sql backups create \
  --instance=crypto-signals-prod \
  --description="Pre-auto-execution deployment backup"

# PostgreSQL direct
pg_dump -U postgres crypto_signals > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Step 2: Blue-Green Deployment**
```bash
# 1. Deploy new version to separate environment (GREEN)
docker-compose -f docker-compose.prod.yml \
  -p crypto-signals-green up -d

# 2. Run migrations
docker-compose -p crypto-signals-green exec backend \
  python3 -c "from db import init_db; init_db()"

# 3. Run smoke tests
curl https://green.cryptosignal.app/health

# 4. Switch traffic (via load balancer or DNS)
# AWS: Update target group
aws elbv2 modify-target-group-attributes \
  --target-group-arn <green-tg> \
  --attributes Key=deregistration_delay.timeout_seconds,Value=30

# GCP: Update backend service
gcloud compute backend-services update crypto-signals \
  --global \
  --enable-health-checks

# 5. Monitor GREEN environment
# Check: CPU, memory, error rates, latency

# 6. If successful, mark GREEN as BLUE (old version)
docker-compose -p crypto-signals down
mv crypto-signals-green crypto-signals
```

**Step 3: Database Migration**
```bash
# Run migration in production environment
docker-compose -p crypto-signals exec backend \
  python3 -c "from db import init_db; init_db()"

# Verify migration
docker-compose -p crypto-signals exec db psql \
  -U crypto_user -d crypto_signals \
  -c "SELECT COUNT(*) FROM auto_execution_audit;"
```

**Step 4: Production Validation**
```bash
# 1. Health checks
curl https://cryptosignal.app/health

# 2. API endpoints
curl -H "Authorization: Bearer prod-key" \
  https://cryptosignal.app/api/signal/BTCUSDT

# 3. Auto-execution endpoints
curl -H "Authorization: Bearer prod-key" \
  https://cryptosignal.app/api/trading/auto-execution/status

# 4. Database connectivity
# Monitor: Connection count, query performance

# 5. Monitor auto-execution audit logs
# AWS: CloudWatch
# GCP: Cloud Logging
# VPS: tail -f logs/auto_execution.log
```

### Post-Deployment Monitoring (48 Hours)
```
Every hour for first 24 hours:
[ ] API response times < 500ms
[ ] Error rate < 0.1%
[ ] Database CPU < 80%
[ ] Memory usage normal
[ ] Auto-execution audit logs flowing
[ ] No SSL certificate errors

Every 4 hours for next 24 hours:
[ ] User signups working
[ ] Trading endpoints functional
[ ] Auto-execution triggers as expected
[ ] Audit logs capturing all attempts
[ ] Notifications (email/SMS) sending
```

---

## 🔄 CI/CD Pipeline (GitHub Actions)

### Setup (One-time)
```bash
# 1. Add repository secrets (Settings > Secrets)
DOCKER_USERNAME=your_docker_username
DOCKER_PASSWORD=your_docker_password
DOCKER_REGISTRY=your.registry.com

AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

PROD_DATABASE_URL=postgresql://...
STAGING_DATABASE_URL=postgresql://...

SLACK_WEBHOOK=https://hooks.slack.com/...
PROD_TEST_API_KEY=...
STAGING_TEST_API_KEY=...
```

### Automated Deployment
```bash
# Workflow triggers on:
# 1. Push to staging branch → Deploy to staging
# 2. Push to main branch → Deploy to production (manual approval)

# Steps:
1. Run tests (backend + frontend)
2. Build Docker images
3. Push to registry
4. Deploy to environment
5. Run smoke tests
6. Notify Slack
7. (Production only) Create deployment record
```

### Monitor Deployment
```bash
# View workflow status
# GitHub: Actions tab

# View logs
git log --oneline
# Look for deployment commits

# Check deployment status
# AWS: aws ecs describe-services ...
# GCP: gcloud run services describe ...
```

---

## ⚠️ Rollback Procedures

### Immediate Rollback (Production Issue)
```bash
# Option 1: Revert to previous Docker image
docker-compose -p crypto-signals down
docker-compose -p crypto-signals up -d \
  --build-arg IMAGE_TAG=previous-stable

# Option 2: Restore database from backup
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier crypto-signals-prod \
  --db-snapshot-identifier crypto-signals-prod-pre-autofx-backup

# Option 3: Quick disable (without full rollback)
UPDATE binance_credentials SET auto_execution_enabled = FALSE;
```

### Staged Rollback (If Issues Develop)
```bash
# 1. Disable feature flag
UPDATE binance_credentials SET auto_execution_enabled = FALSE;

# 2. Monitor for 1 hour
# Check: error rates, user complaints

# 3. If still issues, revert code
git revert <problematic-commit>
git push origin main

# 4. GitHub Actions will auto-deploy
# Monitor: Status checks, logs

# 5. Restore database (if schema changes)
# Use pre-deployment backup
```

### Communication During Rollback
```
1. Slack notification
2. Customer email (if needed)
3. Status page update
4. Post-mortem scheduled
5. Root cause analysis
```

---

## 📊 Post-Deployment Analysis

### First 24 Hours
```
Metrics to review:
- Auto-execution success rate
- Average signal confidence
- Recovery state distribution
- Audit log volume
- Error frequency
- User feedback/support tickets
```

### First Week
```
Performance review:
- Latency percentiles (p50, p95, p99)
- Database performance
- Cache hit rates
- Error patterns
- Feature adoption rate
- Revenue impact
```

### Create Improvement Ticket
```
Title: Post-Deployment Analysis - Auto-Execution
Description:
- Metrics review
- Issues encountered
- Improvements needed
- Team feedback
```

---

## 🔐 Security Checklist (Pre-Deployment)

```
[ ] All secrets in environment variables (not in code)
[ ] Database credentials rotated
[ ] SSL certificates valid
[ ] API keys restricted to IP ranges
[ ] Database backups encrypted
[ ] Access logs enabled
[ ] Rate limiting configured
[ ] SQL injection prevention verified
[ ] CSRF tokens enabled
[ ] Security headers set
[ ] Audit logging enabled
```

---

## 📞 Support & Troubleshooting

### Common Issues

**Issue: Deployment fails at database migration**
```bash
# Check migration status
docker-compose exec db psql -U crypto_user -d crypto_signals \
  -c "\dt auto_execution_audit"

# Manually run migration
docker-compose exec backend python3 -c "from db import init_db; init_db()"
```

**Issue: High database CPU after deployment**
```bash
# Check slow queries
docker-compose exec db psql -U crypto_user -d crypto_signals \
  -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Add indexes if needed
CREATE INDEX idx_auto_exec_user_symbol ON auto_execution_audit(user_id, symbol);
```

**Issue: Auto-execution not triggering**
```bash
# Check audit logs
SELECT * FROM auto_execution_audit WHERE executed = false LIMIT 10;

# Check recovery state
SELECT user_id, recovery_state FROM auto_execution_audit LIMIT 5;

# Verify feature is enabled
SELECT auto_execution_enabled FROM binance_credentials WHERE user_id = 'test';
```

### Escalation Path
```
1. Check logs and error messages
2. Post in #crypto-signals-ops Slack
3. Page on-call engineer
4. Engage database team (if DB related)
5. Contact cloud provider support
```

---

## ✅ Sign-Off

Once deployment is complete and validated:

**Product Lead:** _____________________  Date: _____

**Engineering Lead:** _____________________  Date: _____

**DevOps Lead:** _____________________  Date: _____

---

## 📝 Version History

```
v1.0 - 2026-05-27 - Initial auto-execution deployment guide
```

Questions? Contact: devops@cryptosignal.app
