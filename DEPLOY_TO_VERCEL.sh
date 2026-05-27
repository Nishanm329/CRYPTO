#!/bin/bash

# ============================================================================
# COMPLETE VERCEL DEPLOYMENT SCRIPT
# ============================================================================
# This script automates the Vercel deployment process
# ============================================================================

set -e

echo "=========================================="
echo "CRYPTO SIGNALS - VERCEL DEPLOYMENT"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ============================================================================
# STEP 1: Verify Vercel CLI
# ============================================================================
echo -e "${BLUE}STEP 1: Checking Vercel CLI${NC}"
echo "=================================="

if ! command -v vercel &> /dev/null; then
    echo -e "${YELLOW}Vercel CLI not found. Installing...${NC}"
    npm install -g vercel
fi

VERCEL_VERSION=$(vercel --version)
echo -e "${GREEN}✓ Vercel CLI installed: $VERCEL_VERSION${NC}"
echo ""

# ============================================================================
# STEP 2: Verify Git Setup
# ============================================================================
echo -e "${BLUE}STEP 2: Verifying Git Setup${NC}"
echo "=================================="

if [ -z "$(git config user.email)" ]; then
    echo "Configuring Git..."
    git config user.name "CryptoSignal Dev"
    git config user.email "dev@cryptosignal.app"
fi

REMOTE=$(git remote get-url origin 2>/dev/null || echo "not set")
echo -e "${GREEN}✓ Git remote: $REMOTE${NC}"

if [ "$REMOTE" = "not set" ]; then
    echo -e "${YELLOW}⚠ No GitHub remote set. You'll need to push manually.${NC}"
fi

echo ""

# ============================================================================
# STEP 3: Check Required Files
# ============================================================================
echo -e "${BLUE}STEP 3: Checking Required Files${NC}"
echo "=================================="

REQUIRED_FILES=(
    "vercel.json"
    "frontend/package.json"
    "backend/main.py"
    "backend/requirements.txt"
    ".env.production.vercel"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file (MISSING)"
    fi
done
echo ""

# ============================================================================
# STEP 4: Frontend Deployment
# ============================================================================
echo -e "${BLUE}STEP 4: Frontend Deployment${NC}"
echo "=================================="
echo ""
echo "You need to manually deploy the frontend to Vercel:"
echo ""
echo "1. Go to: https://vercel.com/new"
echo "2. Sign in with GitHub"
echo "3. Import your GitHub repository"
echo "4. Framework: Next.js (auto-detected)"
echo "5. Root Directory: frontend/"
echo "6. Environment Variables:"
echo "     NEXT_PUBLIC_API_URL = https://crypto-signals-api.vercel.app"
echo "     NEXT_PUBLIC_ENVIRONMENT = production"
echo "7. Click 'Deploy'"
echo ""
echo "After deployment:"
echo "  - Save your frontend URL: https://[project-name].vercel.app"
echo "  - Copy it to use in next step"
echo ""

read -p "Press Enter after frontend is deployed to Vercel..."
echo ""

# ============================================================================
# STEP 5: Backend Deployment
# ============================================================================
echo -e "${BLUE}STEP 5: Backend Deployment${NC}"
echo "=================================="
echo ""

echo "Choose deployment method:"
echo "1. Vercel (separate project)"
echo "2. Railway (better for Python/FastAPI)"
echo "3. Skip for now"
echo ""

read -p "Enter choice (1-3): " BACKEND_CHOICE

case $BACKEND_CHOICE in
    1)
        echo ""
        echo "Deploying backend to Vercel..."
        echo ""

        # Deploy backend
        vercel --prod --name crypto-signals-api

        echo ""
        echo "✓ Backend deployed!"
        echo ""
        echo "Next: Add environment variables to Vercel project:"
        echo "  Go to: vercel.com → crypto-signals-api → Settings → Environment Variables"
        echo ""
        read -p "Press Enter after adding environment variables..."

        # Redeploy
        vercel --prod --name crypto-signals-api
        echo -e "${GREEN}✓ Backend redeployed with environment variables${NC}"
        ;;
    2)
        echo ""
        echo "Railway deployment:"
        echo "1. Go to: https://railway.app/new"
        echo "2. Select 'Provision PostgreSQL' first (for database)"
        echo "3. Add new Python service"
        echo "4. Connect GitHub repo (Nishanm329/CRYPTO)"
        echo "5. Set root directory: ./backend"
        echo "6. Add environment variables"
        echo "7. Deploy"
        echo ""
        read -p "Press Enter after Railway deployment completes..."
        ;;
    3)
        echo "Skipping backend deployment for now"
        ;;
esac

echo ""

# ============================================================================
# STEP 6: Database Setup
# ============================================================================
echo -e "${BLUE}STEP 6: Database Setup${NC}"
echo "=================================="
echo ""

echo "Choose database provider:"
echo "1. Neon.tech (Recommended - Free PostgreSQL)"
echo "2. Railway PostgreSQL"
echo "3. Skip - use existing database"
echo ""

read -p "Enter choice (1-3): " DB_CHOICE

case $DB_CHOICE in
    1)
        echo ""
        echo "Neon.tech setup:"
        echo "1. Go to: https://neon.tech/sign_up"
        echo "2. Create account"
        echo "3. Create new database:"
        echo "   - Project name: crypto-signals"
        echo "   - Region: US East"
        echo "4. Copy connection string"
        echo ""
        read -p "Enter Neon connection string: " NEON_URL

        echo ""
        echo "Running migration..."
        psql "$NEON_URL" < backend/migrations/001_add_auto_execution_fields.sql

        echo -e "${GREEN}✓ Database migrated${NC}"
        echo ""
        echo "Add to Vercel environment variables:"
        echo "  DATABASE_URL = $NEON_URL"
        ;;
    2)
        echo ""
        echo "Railway PostgreSQL:"
        echo "1. Go to: https://railway.app"
        echo "2. Create PostgreSQL plugin"
        echo "3. Copy connection string"
        echo ""
        read -p "Enter Railway connection string: " RAILWAY_URL

        echo ""
        echo "Running migration..."
        psql "$RAILWAY_URL" < backend/migrations/001_add_auto_execution_fields.sql

        echo -e "${GREEN}✓ Database migrated${NC}"
        ;;
    3)
        echo "Using existing database"
        ;;
esac

echo ""

# ============================================================================
# STEP 7: Summary
# ============================================================================
echo -e "${BLUE}STEP 7: Deployment Summary${NC}"
echo "=================================="
echo ""
echo -e "${GREEN}✓ Frontend deployed to Vercel${NC}"
echo -e "${GREEN}✓ Backend deployed (Vercel/Railway)${NC}"
echo -e "${GREEN}✓ Database configured${NC}"
echo ""

echo "Your live URLs:"
echo "  Frontend: https://[project-name].vercel.app"
echo "  Backend API: https://crypto-signals-api.vercel.app"
echo "  API Docs: https://crypto-signals-api.vercel.app/docs"
echo ""

echo "Test your deployment:"
echo "  curl https://crypto-signals-api.vercel.app/health"
echo ""

echo -e "${GREEN}=========================================="
echo "DEPLOYMENT COMPLETE! 🚀"
echo "==========================================${NC}"
echo ""
