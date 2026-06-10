# Render.com Backend Deployment - Step-by-Step Guide

## 🎯 Goal
Deploy CryptoSignal API backend to Render.com with PostgreSQL database. Fast, reliable, and free tier available.

**Estimated Time:** 10-15 minutes  
**What You Need:**
- GitHub account (already connected)
- Render.com account (free)

---

## ⚡ QUICK START

### Step 1: Create Render.com Account
**URL:** https://render.com

1. Click **"Sign up"** 
2. Use GitHub to sign up (easiest option)
3. Authorize Render to access your GitHub repos

---

### Step 2: Create New Web Service
1. Click **"New +"** button (top right)
2. Select **"Web Service"**
3. When prompted, search for your repo: `CRYPTO`
4. Select: `Nishanm329/CRYPTO`
5. Click **"Connect"**

---

### Step 3: Configure Deployment Settings

**Basic Info:**
- **Name:** `crypto-signals-api` (or your preferred name)
- **Region:** `Oregon (US West)` (or closest to you)
- **Branch:** `main`
- **Runtime:** `Python 3` (auto-detected)

**Build & Start Commands:**
- **Build Command:** 
  ```
  pip install -r requirements.txt
  ```

- **Start Command:** 
  ```
  cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
  ```

**Plan:** Select `Free` tier (limited but sufficient for MVP)

---

### Step 4: Add Environment Variables

1. Scroll down to **"Environment"** section
2. Click **"Add Environment Variable"** for each item below:

| Name | Value | Notes |
|------|-------|-------|
| `ENVIRONMENT` | `production` | Deployment environment |
| `LOG_LEVEL` | `INFO` | Logging level |
| `PORT` | `8000` | Will be overridden by Render ($PORT) |
| `CORS_ORIGINS` | `https://frontend-ivbkhvgqd-nish-markets.vercel.app` | Your frontend URL |
| `API_KEYS` | `demo-key-public:demo-user` | Demo key for testing |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Resilience setting |
| `CIRCUIT_BREAKER_TIMEOUT` | `60` | Seconds before retry |
| `RATE_LIMIT_SCAN` | `30` | Requests per minute |
| `RATE_LIMIT_SIGNAL` | `60` | Requests per minute |
| `RATE_LIMIT_CHART` | `60` | Requests per minute |
| `RATE_LIMIT_MARKET` | `20` | Requests per minute |
| `PROMETHEUS_ENABLED` | `true` | Metrics collection |

**Optional (if using database features):**
| `DATABASE_URL` | `postgresql://user:pass@host/db` | PostgreSQL connection |
| `DB_POOL_SIZE` | `5` | Connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections |

---

### Step 5: Click Deploy

1. Click **"Create Web Service"** button (bottom)
2. Render will:
   - Clone your GitHub repo
   - Install dependencies from `requirements.txt`
   - Start the service with uvicorn
   - Assign you a free domain

**Build takes ~2-3 minutes**

---

### Step 6: Get Your API URL

Once deployment completes (you'll see green checkmark):

1. Go to **"Settings"** tab
2. Look for **"Render Domain"** section
3. You'll see a URL like: `crypto-signals-api.onrender.com`
4. **This is your live API!**

---

### Step 7: Test Your API

Open a terminal and run:

```bash
# Test if API is running
curl https://crypto-signals-api.onrender.com/health

# Expected response:
# {"status":"ok","environment":"production"}
```

✅ If you get a response, your API is working!

---

### Step 8: Update Frontend API URL (if needed)

If your Render URL is different from what's configured:

1. Go to **Vercel Dashboard** → crypto-signals frontend
2. Go to **Settings** → **Environment Variables**
3. Update `NEXT_PUBLIC_API_URL` to your Render URL:
   ```
   NEXT_PUBLIC_API_URL=https://crypto-signals-api.onrender.com
   ```
4. Vercel will auto-redeploy

---

### Step 9: Enable Auto-Deploy (Optional)

1. In Render dashboard, go to your service
2. Go to **"Settings"** tab
3. Enable **"Auto-Deploy"** (or leave it to manual deploys)

Now every git push to `main` will auto-deploy!

---

## 📊 System Status After Deployment

```
Frontend:  ✅ https://frontend-ivbkhvgqd-nish-markets.vercel.app
Backend:   ✅ https://crypto-signals-api.onrender.com
Database:  ⏳ (Optional, can add later)
API Docs:  📖 https://crypto-signals-api.onrender.com/docs
Health:    ❤️  https://crypto-signals-api.onrender.com/health
```

---

## 🆘 Troubleshooting

### Deployment Failed
**Check logs:**
1. Go to Render Dashboard → Your Service
2. Click **"Logs"** tab
3. Scroll down to see error messages

**Common Issues:**
- **"Module not found"** → Missing dependency in `requirements.txt`
- **"Port already in use"** → Change port in start command
- **"Build timeout"** → Service too heavy; optimize dependencies

### API Not Responding
```bash
# Test the API
curl https://crypto-signals-api.onrender.com/health

# View live logs (from Render dashboard)
# Click Logs tab in your service dashboard
```

### Service Goes to Sleep
- **Free tier limitation:** Render puts free services to sleep after 15 mins of inactivity
- **Solution:** Upgrade to paid tier, or hit API regularly (e.g., every 10 mins with a cron job)
- **Workaround:** Add a monitoring endpoint that pings `/health` every 10 mins

---

## 🔑 Environment Variables Reference

### Essential
- `ENVIRONMENT=production` — Deployment mode
- `LOG_LEVEL=INFO` — Logging verbosity

### API Configuration  
- `CORS_ORIGINS` — Frontend URL for CORS
- `API_KEYS` — Demo key for testing

### Rate Limiting
- `RATE_LIMIT_SCAN=30` — Scan endpoint requests/min
- `RATE_LIMIT_SIGNAL=60` — Signal endpoint requests/min
- `RATE_LIMIT_CHART=60` — Chart endpoint requests/min
- `RATE_LIMIT_MARKET=20` — Market data requests/min

### Resilience
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD=5` — Failures before circuit opens
- `CIRCUIT_BREAKER_TIMEOUT=60` — Seconds before retry attempt

### Optional
- `DATABASE_URL` — PostgreSQL connection string (for database features)
- `SENTRY_DSN` — Error tracking (Sentry)
- `BINANCE_API_KEY` — Binance public API key (optional)
- `BINANCE_API_SECRET` — Binance API secret (optional)

---

## 📝 Quick Reference

| Task | URL/Command |
|------|------------|
| Render Dashboard | https://dashboard.render.com |
| Frontend | https://frontend-ivbkhvgqd-nish-markets.vercel.app |
| API Health | `curl https://crypto-signals-api.onrender.com/health` |
| API Docs | https://crypto-signals-api.onrender.com/docs |
| View Logs | Dashboard → Service → Logs tab |
| Redeploy | Dashboard → Service → Manual Deploy |
| Git Push Deploy | `git push origin main` (auto-deploys if enabled) |

---

## ✅ Completion Checklist

- [ ] Created Render.com account
- [ ] Connected GitHub repo (Nishanm329/CRYPTO)
- [ ] Set build command: `pip install -r requirements.txt`
- [ ] Set start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] Added environment variables
- [ ] Deployment successful (green checkmark)
- [ ] Got Render domain URL
- [ ] Tested `/health` endpoint (got 200 response)
- [ ] Updated frontend `NEXT_PUBLIC_API_URL` (if needed)
- [ ] Frontend connects to backend without errors

**Once all checked, you're LIVE! 🚀**

---

## 🔄 Adding a PostgreSQL Database (Optional)

If you want to add database persistence:

1. In Render Dashboard, click **"New +"** → **"PostgreSQL"**
2. Name it: `crypto-signals-db`
3. Render will create it and add `DATABASE_URL` to your service automatically
4. In your service settings, the `DATABASE_URL` will be pre-filled

---

## 💡 Pro Tips

1. **Keep dependencies minimal:** Only add libraries you actually use. Render builds faster with fewer dependencies.

2. **Use `requirements-prod.txt`** (optional): If you have dev-only dependencies, create a production-only requirements file.

3. **Monitor logs regularly:** Check Logs tab to catch errors early.

4. **Set up monitoring:** Use `/health` endpoint with external monitoring tool (e.g., UptimeRobot) to alert on downtime.

5. **Version your API:** Add `API_VERSION` env var to track deployments.

---

**Last Updated:** June 10, 2026  
**Status:** Ready to Deploy 🚀

