# Vercel Deployment Guide - Auto-Execution Feature

## Overview

This guide covers deploying the CryptoSignal AI auto-execution feature to Vercel, including the Next.js frontend and FastAPI backend.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Vercel (Edge Network)                      │
├──────────────────────────────────┬──────────────────────────────┤
│   Frontend (Next.js)             │  Backend API (Serverless)    │
│ - Pages & Components             │ - FastAPI Endpoints          │
│ - AutoExecutionSettings.js        │ - /api/trading/...           │
│ - Static Assets                  │ - /api/signal/...            │
│ - Client-side Routing            │ - Database Integration       │
└──────────────────────────────────┴──────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────────┐
│              PostgreSQL + TimescaleDB (External)                  │
│                                                                   │
│  Tables:                                                          │
│  - signals_history                                               │
│  - binance_credentials                                           │
│  - auto_execution_audit (20+ fields)                             │
│  - trades, user_preferences, error_logs                          │
└──────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **GitHub Account** - Required to connect repo to Vercel
2. **Vercel Account** - Free tier or Pro plan
3. **PostgreSQL Database** - Use Neon.tech (free) or Railway
4. **Domain** (optional) - For custom domain configuration

## Deployment Steps

### Step 1: Prepare Repository

```bash
# 1. Initialize git (if not done)
git init
git config user.name "Your Name"
git config user.email "you@example.com"

# 2. Create GitHub repo
# Go to github.com/new and create "crypto-signals"

# 3. Add remote and push
git remote add origin https://github.com/YOUR_USERNAME/crypto-signals.git
git add .
git commit -m "Initial commit: Auto-execution feature production-ready"
git push -u origin main
```

### Step 2: Set Up Database

**Option A: Neon (Recommended for Free Tier)**
```bash
# 1. Create account at neon.tech
# 2. Create new database
# 3. Copy connection string: postgresql://user:password@host/dbname

# 4. Run migrations
psql "postgresql://user:password@host/dbname" < backend/migrations/001_add_auto_execution_fields.sql

# 5. Verify tables
psql "postgresql://user:password@host/dbname" -c "\dt"
```

**Option B: Railway (Alternative)**
- Go to railway.app
- Create new project → PostgreSQL
- Configure database
- Get connection string

### Step 3: Deploy to Vercel

#### Method 1: Vercel Dashboard (Easiest)

1. **Go to Vercel.com**
   - Sign in with GitHub
   - Click "New Project"

2. **Import GitHub Repository**
   - Select "crypto-signals" repo
   - Framework: Next.js (auto-detected)
   - Root Directory: `frontend/`

3. **Configure Environment Variables**
   
   In Vercel Project Settings → Environment Variables:
   ```
   NEXT_PUBLIC_API_URL = https://crypto-signals-api.vercel.app
   NEXT_PUBLIC_ENVIRONMENT = production
   DATABASE_URL = postgresql://user:password@host/dbname
   DB_NAME = crypto_signals
   DB_USER = postgres
   DB_PASSWORD = your_password
   DB_HOST = your_host
   DB_PORT = 5432
   
   API_KEYS = prod-key-1:prod-user-1,prod-key-2:prod-user-2
   JWT_SECRET = your-jwt-secret-key
   JWT_ALGORITHM = HS256
   JWT_EXPIRE_HOURS = 24
   
   ENVIRONMENT = production
   LOG_LEVEL = info
   
   BINANCE_API_KEY = your_binance_key
   BINANCE_API_SECRET = your_binance_secret
   BINANCE_TEST_MODE = false
   
   ENABLE_AUTO_EXECUTION = true
   ENABLE_PAPER_TRADING = true
   ENABLE_LIVE_TRADING = false
   ```

4. **Deploy**
   - Click "Deploy"
   - Vercel builds and deploys automatically
   - Frontend available at: https://crypto-signals.vercel.app

#### Method 2: Vercel CLI

```bash
# 1. Install Vercel CLI
npm i -g vercel

# 2. Link project to Vercel
cd /path/to/crypto-signals
vercel link

# 3. Add environment variables
vercel env add NEXT_PUBLIC_API_URL
vercel env add DATABASE_URL
# ... add all required variables

# 4. Deploy
vercel --prod
```

### Step 4: Backend API Deployment

For FastAPI backend on Vercel, use one of these approaches:

#### Approach A: Separate Vercel Project (Recommended)

```bash
# 1. Create separate GitHub branch for backend
git checkout -b backend-api

# 2. Restructure backend as Vercel serverless:
mkdir -p api
# Move Python files to api/ directory
# Vercel treats api/ folder as serverless functions

# 3. Create api/index.py as entry point
cat > api/index.py << 'EOF'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
sys.path.insert(0, '/var/task')

# Import your FastAPI app
from backend.main import app

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://crypto-signals.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}
EOF

# 4. Deploy backend separately
vercel --prod --name crypto-signals-api
```

#### Approach B: AWS Lambda / Railway

```bash
# Alternative: Deploy backend to separate service
# Option 1: AWS Lambda with Zappa
pip install zappa
zappa init
zappa deploy production

# Option 2: Railway
# 1. Go to railway.app
# 2. Create new project
# 3. Select Python + FastAPI
# 4. Connect GitHub repo
# 5. Deploy
```

### Step 5: Update Frontend API URL

After backend deployment, update environment variable:

**In Vercel Dashboard:**
1. Project Settings → Environment Variables
2. Update `NEXT_PUBLIC_API_URL` to actual backend URL
3. Redeploy frontend: `vercel --prod`

### Step 6: Connect Custom Domain (Optional)

```bash
# 1. In Vercel Dashboard, go to Domains
# 2. Add custom domain (e.g., cryptosignal.app)
# 3. Update DNS records with values from Vercel
# 4. Wait 24-48 hours for DNS propagation
```

## Testing Deployment

### Health Check
```bash
curl https://crypto-signals-api.vercel.app/health
# Expected: {"status":"ok"}

curl https://crypto-signals.vercel.app/
# Expected: Next.js frontend loads
```

### API Endpoint Test
```bash
curl -H "Authorization: Bearer prod-key-1" \
  https://crypto-signals-api.vercel.app/api/trading/auto-execution/status
# Expected: 200 OK with auto_execution settings
```

### E2E Test
1. Open https://crypto-signals.vercel.app in browser
2. Navigate to Settings → Auto-Execution
3. Enable auto-execution
4. Set wallet balance to $5000
5. Verify settings saved and stats display

## Monitoring & Logging

### Vercel Analytics
- **Dashboard:** vercel.com/dashboard
- **Metrics:** Page load time, edge request duration, data transfer
- **Real-time logs:** Deployments → Select deployment → Logs

### Application Logs
```bash
# View deployment logs
vercel logs crypto-signals

# View API function logs
vercel logs crypto-signals-api

# Real-time monitoring
vercel logs crypto-signals --follow
```

## Environment Variables Reference

| Variable | Required | Example |
|----------|----------|---------|
| `NEXT_PUBLIC_API_URL` | Yes | `https://crypto-signals-api.vercel.app` |
| `NEXT_PUBLIC_ENVIRONMENT` | No | `production` |
| `DATABASE_URL` | Yes | `postgresql://...` |
| `API_KEYS` | Yes | `key1:user1,key2:user2` |
| `JWT_SECRET` | Yes | Generate: `openssl rand -hex 32` |
| `BINANCE_API_KEY` | No | Your Binance API key |
| `BINANCE_API_SECRET` | No | Your Binance API secret |
| `ENVIRONMENT` | Yes | `production` |

## Troubleshooting

### Issue: 404 on Frontend
**Cause:** Vercel can't find Next.js build  
**Fix:** Ensure `vercel.json` has correct `buildCommand` and `rootDirectory`

### Issue: API Returns 500
**Cause:** Database connection failed  
**Fix:** Verify `DATABASE_URL` in environment variables

### Issue: CORS Errors
**Cause:** Frontend and backend on different origins  
**Fix:** Update CORS middleware with correct frontend URL

### Issue: Slow Performance
**Cause:** Cold start on serverless functions  
**Fix:** Use Railway or separate backend service for better performance

## Cost Estimation (Monthly)

| Service | Tier | Cost |
|---------|------|------|
| Vercel Frontend | Hobby | Free |
| Vercel API | Hobby | Free* |
| PostgreSQL (Neon) | Free | Free |
| Total | | **$0-5/mo** |

*Free tier includes 100 serverless function invocations/day. For production, upgrade to Pro ($20/mo).

## Rollback Plan

If deployment causes issues:

```bash
# 1. Rollback to previous deployment
vercel rollback crypto-signals

# 2. Select previous successful deployment
# 3. Confirm rollback

# Or manually:
# Go to Vercel Dashboard → Deployments
# Click on previous version → Promote to Production
```

## Next Steps

1. ✅ Initialize Git repo
2. ✅ Create GitHub repo
3. ✅ Set up PostgreSQL database
4. ✅ Deploy frontend to Vercel
5. ✅ Deploy backend (Lambda/Railway/separate Vercel project)
6. ✅ Configure environment variables
7. ✅ Run E2E tests
8. ✅ Set up custom domain
9. ✅ Configure monitoring
10. ✅ Document deployment for team

## Support

- **Vercel Docs:** https://vercel.com/docs
- **Next.js Docs:** https://nextjs.org/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **PostgreSQL Docs:** https://neon.tech/docs

---

**Deployment Status:** Ready for production  
**Last Updated:** 2026-05-27  
**Auto-Execution Version:** 1.0.0
