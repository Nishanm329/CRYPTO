# Vercel Deployment Checklist - Auto-Execution Feature

## Pre-Deployment (Local Validation)

- [x] Local tests passing: 44/44 ✓
- [x] Database migrations created ✓
- [x] Frontend components ready ✓
- [x] Backend endpoints tested ✓
- [x] Environment configuration templated ✓
- [x] Git repository initialized ✓
- [ ] Code review completed
- [ ] Security audit completed
- [ ] Performance baseline established

## Step 1: GitHub Setup (15 minutes)

- [ ] Create GitHub account (if needed): github.com
- [ ] Create new repository: https://github.com/new
  - Repository name: `crypto-signals`
  - Description: `CryptoSignal AI - Auto-Execution Trading Feature`
  - Privacy: Public (for deployment) or Private (more secure)
  - Add .gitignore: Python, Node
  - Add license: MIT

- [ ] Clone local repo to GitHub:
  ```bash
  git remote add origin https://github.com/YOUR_USERNAME/crypto-signals.git
  git branch -M main
  git push -u origin main
  ```

- [ ] Verify on GitHub:
  - Visit https://github.com/YOUR_USERNAME/crypto-signals
  - Confirm files are visible
  - Check branch is "main"

## Step 2: Database Setup (20 minutes)

### Option A: Neon.tech (Recommended)

- [ ] Create account: https://neon.tech
- [ ] Create new project
  - Database name: `crypto_signals`
  - Region: US East (or closest to you)
  - Postgres version: 15

- [ ] Copy connection string
  - Format: `postgresql://user:password@host/dbname?sslmode=require`
  - Save securely

- [ ] Run migrations:
  ```bash
  # Install psql if needed
  brew install postgresql@15
  
  # Run migration
  psql "YOUR_CONNECTION_STRING" < backend/migrations/001_add_auto_execution_fields.sql
  
  # Verify
  psql "YOUR_CONNECTION_STRING" -c "\dt"
  # Should show: signals_history, user_preferences, error_logs, trades, binance_credentials, auto_execution_audit
  ```

- [ ] Test connection:
  ```bash
  psql "YOUR_CONNECTION_STRING" -c "SELECT version();"
  ```

### Option B: Railway (Alternative)

- [ ] Create account: https://railway.app
- [ ] Create new project → PostgreSQL
- [ ] Configure credentials
- [ ] Get connection string
- [ ] Run same migrations as Option A

## Step 3: Generate Secrets (5 minutes)

- [ ] Generate JWT secret:
  ```bash
  openssl rand -hex 32
  # Save output - you'll need this for Vercel
  ```

- [ ] Generate API keys:
  ```bash
  # For production users (format: key:user)
  # Example: prod-key-1:prod-user-1
  ```

- [ ] Prepare Binance credentials (optional for testing):
  - [ ] API Key (from Binance Account)
  - [ ] API Secret (from Binance Account)

## Step 4: Vercel Project Setup (10 minutes)

### Frontend Project

- [ ] Go to Vercel.com
- [ ] Sign in with GitHub
- [ ] Click "New Project"
- [ ] Select `crypto-signals` repository
- [ ] Framework: Next.js (should auto-detect)
- [ ] Root Directory: `frontend/`
- [ ] Build Command: `npm run build`
- [ ] Install Command: `npm install`
- [ ] Output Directory: `.next`

- [ ] **Add Environment Variables** (see Step 5)
  - [ ] NEXT_PUBLIC_API_URL
  - [ ] NEXT_PUBLIC_ENVIRONMENT

- [ ] Click "Deploy"
- [ ] Wait for deployment (2-5 minutes)
- [ ] Note deployed URL: `https://[project-name].vercel.app`

## Step 5: Configure Environment Variables (15 minutes)

### In Vercel Dashboard

Go to: **Project Settings → Environment Variables**

#### Frontend Variables
```
NEXT_PUBLIC_API_URL = https://crypto-signals-api.vercel.app
NEXT_PUBLIC_ENVIRONMENT = production
```

#### Backend Variables
```
DATABASE_URL = postgresql://user:password@host/dbname
ENVIRONMENT = production
LOG_LEVEL = info

API_KEYS = demo-key-public:demo-user
JWT_SECRET = [from openssl command above]
JWT_ALGORITHM = HS256
JWT_EXPIRE_HOURS = 24

ENABLE_AUTO_EXECUTION = true
ENABLE_PAPER_TRADING = true
ENABLE_LIVE_TRADING = false

VERY_HIGH_CONFIDENCE_THRESHOLD = 85
HIGH_CONFIDENCE_THRESHOLD = 75

AUTO_EXEC_VERY_HIGH_SIZE = 1.0
AUTO_EXEC_HIGH_SIZE = 0.8
AUTO_EXEC_RECOVERY_SIZE = 0.5
```

- [ ] Verify all variables are set
- [ ] Click "Save"

## Step 6: Backend Deployment (20 minutes)

### Option A: Separate Vercel Project (Recommended)

```bash
# 1. Create new Vercel project for backend
vercel --prod --name crypto-signals-api

# 2. Add environment variables same as Step 5
# In Vercel Dashboard: crypto-signals-api → Settings → Environment Variables

# 3. Deploy
vercel --prod --name crypto-signals-api
```

- [ ] Backend deployed at: `https://crypto-signals-api.vercel.app`
- [ ] Test health endpoint:
  ```bash
  curl https://crypto-signals-api.vercel.app/health
  # Expected: {"status":"ok"}
  ```

### Option B: Railway (Alternative)

- [ ] Go to https://railway.app
- [ ] Create new project
- [ ] Connect GitHub repo
- [ ] Select Python + FastAPI template
- [ ] Set environment variables
- [ ] Deploy

- [ ] Get deployed URL from Railway dashboard
- [ ] Update NEXT_PUBLIC_API_URL in Vercel frontend

## Step 7: Update Frontend with Backend URL (5 minutes)

- [ ] Get backend URL from deployment
- [ ] Go to Vercel → Frontend project → Settings → Environment Variables
- [ ] Update `NEXT_PUBLIC_API_URL` with actual backend URL
- [ ] Redeploy frontend:
  ```bash
  vercel --prod
  ```

## Step 8: Testing in Production (20 minutes)

### Health Checks

- [ ] Frontend loads: https://[project-name].vercel.app
- [ ] Backend health: https://crypto-signals-api.vercel.app/health
- [ ] API docs: https://crypto-signals-api.vercel.app/docs

### Functional Tests

```bash
# Get auto-execution status
curl -H "Authorization: Bearer demo-key-public" \
  https://crypto-signals-api.vercel.app/api/trading/auto-execution/status
# Expected: 200 OK with auto_execution_enabled: false

# Enable auto-execution
curl -X PUT \
  -H "Authorization: Bearer demo-key-public" \
  "https://crypto-signals-api.vercel.app/api/trading/auto-execution?auto_execution_enabled=true"
# Expected: 200 OK

# Update wallet balance
curl -X POST \
  -H "Authorization: Bearer demo-key-public" \
  "https://crypto-signals-api.vercel.app/api/trading/wallet/balance?wallet_balance=5000"
# Expected: 200 OK

# Get signal
curl -H "Authorization: Bearer demo-key-public" \
  "https://crypto-signals-api.vercel.app/api/signal/BTCUSDT"
# Expected: 200 OK or 404 (if no signal)
```

### E2E Testing (Browser)

- [ ] Open frontend in browser
- [ ] Navigate to Settings
- [ ] Toggle auto-execution ON
- [ ] Update wallet balance to $5000
- [ ] Verify changes persist
- [ ] Check stats display
- [ ] Test error handling (disable auto-execution, toggle again)

## Step 9: Monitoring Setup (10 minutes)

### Vercel Dashboard

- [ ] Enable analytics:
  - Project Settings → Analytics
  - View real-time metrics

- [ ] Set up error tracking:
  - Deployments tab → Select deployment
  - Check "Logs" section

- [ ] Configure notifications:
  - Settings → Notifications
  - Email on failed deployment: ✓

### Application Logs

```bash
# View deployment logs
vercel logs crypto-signals

# View API logs
vercel logs crypto-signals-api

# Follow logs in real-time
vercel logs crypto-signals --follow
```

## Step 10: Staging Validation (24 hours)

- [ ] Monitor error rates (should be 0%)
- [ ] Check API response times (<500ms)
- [ ] Verify auto-execution triggers work
- [ ] Monitor database connections
- [ ] Check audit logs for execution attempts
- [ ] No SSL certificate errors
- [ ] No database connection errors
- [ ] All endpoints responding

**Validation Metrics:**
- [ ] Uptime: 100%
- [ ] Error Rate: < 0.1%
- [ ] P95 Latency: < 500ms
- [ ] Database CPU: < 50%
- [ ] Memory usage: < 100MB

## Step 11: Custom Domain Setup (Optional, 5 minutes)

- [ ] Purchase domain (registrar of choice)
- [ ] Go to Vercel → Domains
- [ ] Add domain: `cryptosignal.app`
- [ ] Update DNS records:
  - Copy values from Vercel
  - Update registrar DNS settings
  - Wait 24-48 hours for propagation

- [ ] Verify domain:
  ```bash
  curl https://cryptosignal.app
  # Should redirect to Vercel
  ```

## Step 12: Production Sign-Off (5 minutes)

- [ ] Product Lead: _________________ Date: _______
- [ ] Engineering Lead: _________________ Date: _______
- [ ] DevOps Lead: _________________ Date: _______

### Approval Notes
```
[ ] Code review passed
[ ] Security review passed
[ ] Performance baselines met
[ ] Monitoring configured
[ ] Rollback plan documented
[ ] Team trained on feature
[ ] Documentation complete
[ ] Support team briefed
```

## Post-Deployment

- [ ] Create deployment record (date, version, URL)
- [ ] Update documentation with production URLs
- [ ] Brief team on auto-execution feature
- [ ] Set up on-call rotation for monitoring
- [ ] Schedule 1-week post-launch review
- [ ] Create GitHub issue for feature feedback

## Rollback Plan (If Needed)

```bash
# Option 1: Rollback deployment
vercel rollback crypto-signals

# Option 2: Manual deployment switch
# In Vercel Dashboard → Deployments
# Click on previous version → "Promote to Production"

# Option 3: Disable feature immediately
# In Vercel → Environment Variables
# Set ENABLE_AUTO_EXECUTION = false
# Redeploy
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| 404 on frontend | Build failed | Check Vercel logs, run `npm run build` locally |
| API 500 errors | DB connection failed | Verify DATABASE_URL, test connection with psql |
| CORS errors | Missing origin | Add frontend URL to CORS_ORIGINS |
| Slow responses | Cold start | Use Railway for persistent backend |
| Blank screen | Missing env vars | Verify all NEXT_PUBLIC_* variables set |

## Estimated Timeline

- Pre-Deployment: 1 hour ✓
- GitHub Setup: 15 minutes
- Database Setup: 20 minutes
- Secrets Generation: 5 minutes
- Vercel Setup: 10 minutes
- Environment Variables: 15 minutes
- Backend Deployment: 20 minutes
- Frontend Update: 5 minutes
- Production Testing: 20 minutes
- Monitoring Setup: 10 minutes
- Staging Validation: 24 hours
- **Total: ~48 hours including validation period**

---

**Status: Ready for Deployment** 🚀  
**Date: 2026-05-27**  
**Feature: Auto-Execution v1.0.0**
