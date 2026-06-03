# Railway Backend Deployment - Step-by-Step Guide

## 🎯 Goal
Deploy CryptoSignal API backend to Railway, connect to Neon PostgreSQL database, and go live.

**Estimated Time:** 10-15 minutes  
**What You Need:**
- GitHub account (already connected)
- Neon PostgreSQL connection string (already provided)

---

## ⚡ QUICK START

### Step 1: Go to Railway.app
**URL:** https://railway.app

1. Click **"New Project"**
2. Click **"Deploy from GitHub"** 
3. When prompted to choose a repository:
   - Search for: `CRYPTO`
   - Select: `Nishanm329/CRYPTO`
   - Click **"Deploy Now"**

Railway will auto-detect the `Procfile` and start building!

---

### Step 2: Wait for Initial Build
- Railway will build for ~2-3 minutes
- You'll see a blue progress bar
- Once complete, you'll see: **"Build Successful"** ✅

---

### Step 3: Add Database
Railway will show your project dashboard. Now add PostgreSQL:

1. Click **"+ Add"** button (in the project)
2. Select **"Add existing service"** or **"PostgreSQL"**
3. Choose **"Add existing service"** 
4. Skip creating a new PostgreSQL (we'll use Neon)

---

### Step 4: Configure Environment Variables

Click **"Variables"** tab in your project.

Add these variables one by one:

| Name | Value |
|------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql://neondb_owner:npg_Qqc6l5JjGhgE@ep-hidden-meadow-apl3bwz7.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require` |
| `FRONTEND_URL` | `https://frontend-ivbkhvgqd-nish-markets.vercel.app` |
| `API_TITLE` | `CryptoSignal Trading API` |
| `API_VERSION` | `1.0.0` |
| `DEBUG` | `false` |
| `DB_POOL_SIZE` | `5` |
| `DB_MAX_OVERFLOW` | `10` |
| `LOG_LEVEL` | `INFO` |

**How to Add Each Variable:**
1. Click **"New Variable"** button
2. Enter Name (e.g., `ENVIRONMENT`)
3. Enter Value (e.g., `production`)
4. Press Enter or click checkmark
5. Repeat for each variable

---

### Step 5: Redeploy with Environment Variables

Once all variables are added:
1. Look for **"Deployments"** section
2. Click **"Redeploy"** or **"Deploy Latest"**
3. Wait for build to complete (~2 minutes)

You'll see: **"Build Successful"** ✅

---

### Step 6: Get Your API URL

Once deployment is complete:
1. Go to **"Settings"** tab
2. Look for **"Domains"** section
3. You'll see a URL like: `crypto-signals-api-railway.app`
4. Copy this URL - this is your live API!

**Your API is now live at:**
```
https://crypto-signals-api-railway.app
```

---

### Step 7: Test Your API

Open a terminal and run:

```bash
# Test if API is running
curl https://crypto-signals-api-railway.app/health

# Expected response:
# {"status":"ok","environment":"production"}
```

If you get a response like above, your API is working! ✅

---

### Step 8: Run Database Migration

The migration will set up tables in your PostgreSQL database.

**Option A: Via Railway CLI** (if you have it installed)
```bash
railway link  # Select your crypto-signals project
railway run "cd backend && python -m alembic upgrade head"
```

**Option B: Via Terminal**
```bash
# Using your Neon connection string directly
psql "postgresql://neondb_owner:npg_Qqc6l5JjGhgE@ep-hidden-meadow-apl3bwz7.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require" \
  -f backend/migrations/001_add_auto_execution_fields.sql
```

**Option C: Via psql (if you prefer GUI)**
1. Open your Neon.tech dashboard
2. Go to SQL Editor
3. Copy-paste the SQL from `backend/migrations/001_add_auto_execution_fields.sql`
4. Run the query

---

### Step 9: Update Frontend (if needed)

If your Railway API URL is different from `https://crypto-signals-api.vercel.app`:

1. Go to **Vercel Dashboard** → crypto-signals frontend project
2. Go to **Settings** → **Environment Variables**
3. Update `NEXT_PUBLIC_API_URL` to your Railway URL
4. Vercel will auto-redeploy

**Current Frontend API URL:**
```
NEXT_PUBLIC_API_URL=https://crypto-signals-api.vercel.app
```

---

### Step 10: Final Testing

Go to your frontend:
```
https://frontend-ivbkhvgqd-nish-markets.vercel.app
```

Verify these work:
- [ ] Page loads without errors
- [ ] Can see Dashboard
- [ ] Signal Scanner loads
- [ ] Chart renders
- [ ] Can navigate without 404 errors

**Congratulations! Your system is live! 🎉**

---

## 🆘 Troubleshooting

### API Deployment Failed
**Check logs:**
1. Go to Railway Dashboard → Your Project
2. Click **"Deployments"** tab
3. Click the failed deployment
4. Scroll down to see error logs

**Common Issues:**
- Missing environment variables → Add them and redeploy
- Database connection error → Check DATABASE_URL format
- Python version issue → Verify requirements.txt

### API Not Responding
```bash
# Check if Railway service is running
curl https://crypto-signals-api-railway.app/health

# View Railway logs
railway logs
```

### Database Migration Failed
- Verify connection string is correct
- Check Neon dashboard for active connections
- Try running migration again

### Frontend Can't Connect to API
- Verify `NEXT_PUBLIC_API_URL` in Vercel environment
- Check Railway API is running: `curl /health`
- Check browser console for CORS errors

---

## 📊 System Status After Deployment

```
Frontend:  ✅ https://frontend-ivbkhvgqd-nish-markets.vercel.app
Backend:   ✅ https://crypto-signals-api-railway.app  (your URL)
Database:  ✅ Neon PostgreSQL
API Docs:  📖 https://crypto-signals-api-railway.app/docs
Health:    ❤️  https://crypto-signals-api-railway.app/health
```

---

## 🎓 What Just Happened

1. **Frontend Deployed:** Next.js app on Vercel CDN (fast)
2. **Backend Deployed:** FastAPI on Railway containers (scalable)
3. **Database Connected:** Neon PostgreSQL (reliable)
4. **Auto-scaling:** Railway scales automatically with traffic
5. **Monitoring:** View logs and metrics in Railway dashboard
6. **CI/CD:** Push to `main` branch → Auto-deploys

---

## 📞 Quick Reference

| Task | Command/URL |
|------|-------------|
| View Railway Dashboard | https://railway.app |
| Frontend | https://frontend-ivbkhvgqd-nish-markets.vercel.app |
| API Health | curl https://crypto-signals-api-railway.app/health |
| API Docs | https://crypto-signals-api-railway.app/docs |
| View Logs | `railway logs` |
| Git Push Deploy | `git push origin main` |

---

## ✅ Completion Checklist

- [ ] Created Railway project
- [ ] Connected GitHub repo
- [ ] Waited for initial build
- [ ] Added all environment variables
- [ ] Redeployed with variables
- [ ] Got API URL
- [ ] Tested `/health` endpoint
- [ ] Ran database migration
- [ ] Tested frontend
- [ ] Verified signal generation works

**Once all checked, you're LIVE! 🚀**

---

**Questions?** Check the logs in Railway dashboard or feel free to ask!
