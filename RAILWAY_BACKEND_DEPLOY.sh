#!/bin/bash

# ============================================================================
# RAILWAY BACKEND DEPLOYMENT SCRIPT
# ============================================================================
# This script automates the Railway backend deployment process for CryptoSignal
# ============================================================================

set -e

echo "=========================================="
echo "CRYPTO SIGNALS - RAILWAY BACKEND DEPLOYMENT"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ============================================================================
# STEP 1: Environment Setup
# ============================================================================
echo -e "${BLUE}STEP 1: Environment Setup${NC}"
echo "=================================="

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo -e "${YELLOW}Creating .env.production for Railway...${NC}"
    cat > .env.production << 'EOF'
# Railway Environment Variables for CryptoSignal Backend
ENVIRONMENT=production

# Database (use Neon PostgreSQL connection string)
# Format: postgresql://username:password@host:port/dbname?sslmode=require
DATABASE_URL=postgresql://YOUR_NEON_CONNECTION_STRING_HERE

# Frontend URL (update with your actual frontend URL)
FRONTEND_URL=https://frontend-ivbkhvgqd-nish-markets.vercel.app

# API Configuration
API_TITLE=CryptoSignal Trading API
API_VERSION=1.0.0
DEBUG=false

# Database Pool Configuration
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
SQL_ECHO=false

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO
EOF
    echo -e "${GREEN}✓ Created .env.production${NC}"
else
    echo -e "${GREEN}✓ .env.production already exists${NC}"
fi

echo ""

# ============================================================================
# STEP 2: Install Railway CLI
# ============================================================================
echo -e "${BLUE}STEP 2: Installing Railway CLI${NC}"
echo "=================================="

if ! command -v railway &> /dev/null; then
    echo -e "${YELLOW}Railway CLI not found. Installing...${NC}"
    npm install -g railway 2>/dev/null || {
        echo -e "${YELLOW}Using curl to install Railway CLI...${NC}"
        curl -L https://railway.app/install.sh | bash
    }
fi

RAILWAY_VERSION=$(railway --version 2>/dev/null || echo "unknown")
echo -e "${GREEN}✓ Railway CLI installed: $RAILWAY_VERSION${NC}"
echo ""

# ============================================================================
# STEP 3: Railway Project Setup
# ============================================================================
echo -e "${BLUE}STEP 3: Railway Project Setup${NC}"
echo "=================================="
echo ""
echo "You need to manually set up the Railway project:"
echo ""
echo "1. Go to: https://railway.app"
echo "2. Click 'New Project'"
echo "3. Select 'Deploy from GitHub'"
echo "4. Connect your GitHub account and select: Nishanm329/CRYPTO"
echo "5. Railway will auto-detect the Procfile and deploy"
echo ""
echo "After creating the project:"
echo "  - Copy your Railway Project ID from the dashboard"
echo "  - Or use: railway link (in this directory)"
echo ""

read -p "Have you created the Railway project? (y/n): " PROJECT_CREATED

if [ "$PROJECT_CREATED" != "y" ]; then
    echo ""
    echo "Please create a Railway project first at https://railway.app/new"
    echo "Then run this script again."
    exit 0
fi

echo ""

# ============================================================================
# STEP 4: Link Railway Project
# ============================================================================
echo -e "${BLUE}STEP 4: Linking Railway Project${NC}"
echo "=================================="

if railway whoami &> /dev/null; then
    echo -e "${GREEN}✓ Already logged into Railway${NC}"
else
    echo -e "${YELLOW}Logging into Railway...${NC}"
    railway login
fi

# Check if project is already linked
if [ -f ".railway/config.json" ]; then
    echo -e "${GREEN}✓ Railway project already linked${NC}"
else
    echo -e "${YELLOW}Linking to Railway project...${NC}"
    railway link || {
        echo -e "${YELLOW}Could not auto-link. You'll need to set PROJECT_ID in Railway dashboard.${NC}"
    }
fi

echo ""

# ============================================================================
# STEP 5: Configure Database
# ============================================================================
echo -e "${BLUE}STEP 5: Configure PostgreSQL Database${NC}"
echo "=================================="
echo ""
echo "Choose your database provider:"
echo ""
echo "1. Use Neon.tech PostgreSQL (Recommended)"
echo "2. Create Railway PostgreSQL"
echo "3. Skip - I'll configure manually"
echo ""

read -p "Enter choice (1-3): " DB_CHOICE

case $DB_CHOICE in
    1)
        echo ""
        echo -e "${YELLOW}Using Neon.tech PostgreSQL${NC}"
        echo ""
        echo "Your Neon connection string:"
        echo "postgresql://neondb_owner:npg_Qqc6l5JjGhgE@ep-hidden-meadow-apl3bwz7.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"
        echo ""
        echo "Add this to Railway Environment Variables:"
        echo "  Name: DATABASE_URL"
        echo "  Value: postgresql://neondb_owner:npg_Qqc6l5JjGhgE@ep-hidden-meadow-apl3bwz7.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"
        echo ""
        echo "Instructions:"
        echo "  1. Go to Railway Dashboard → Your Project → Variables"
        echo "  2. Click 'Add Variable'"
        echo "  3. Paste the DATABASE_URL"
        echo ""
        read -p "Press Enter after adding DATABASE_URL to Railway..."
        ;;
    2)
        echo ""
        echo "Creating PostgreSQL on Railway..."
        echo ""
        echo "1. Go to Railway Dashboard → Your Project"
        echo "2. Click '+ Add Service' → 'PostgreSQL'"
        echo "3. Railway will automatically create DATABASE_URL variable"
        echo "4. Once created, you'll see the connection string"
        echo ""
        read -p "Press Enter after creating PostgreSQL on Railway..."
        ;;
    3)
        echo ""
        echo "You'll need to configure the database manually in Railway dashboard"
        ;;
esac

echo ""

# ============================================================================
# STEP 6: Set Environment Variables
# ============================================================================
echo -e "${BLUE}STEP 6: Configure Environment Variables${NC}"
echo "=================================="
echo ""
echo "Add these environment variables to Railway:"
echo ""
echo "  ENVIRONMENT = production"
echo "  FRONTEND_URL = https://frontend-ivbkhvgqd-nish-markets.vercel.app"
echo "  API_TITLE = CryptoSignal Trading API"
echo "  API_VERSION = 1.0.0"
echo "  DEBUG = false"
echo "  DB_POOL_SIZE = 5"
echo "  DB_MAX_OVERFLOW = 10"
echo "  SQL_ECHO = false"
echo "  LOG_LEVEL = INFO"
echo ""
echo "Instructions:"
echo "  1. Go to Railway Dashboard → Your Project → Variables"
echo "  2. Click 'Add Variable' for each item above"
echo "  3. Railway will auto-use DATABASE_URL from PostgreSQL"
echo ""
read -p "Press Enter after adding all environment variables..."

echo ""

# ============================================================================
# STEP 7: Deploy
# ============================================================================
echo -e "${BLUE}STEP 7: Deployment${NC}"
echo "=================================="
echo ""
echo "Your backend will deploy automatically when you:"
echo "  1. Push changes to GitHub (main branch)"
echo "  2. Or manually deploy from Railway dashboard"
echo ""
echo "To check deployment status:"
echo "  - Go to Railway dashboard"
echo "  - Select your project"
echo "  - View the deployment logs"
echo ""

# ============================================================================
# STEP 8: Database Migration
# ============================================================================
echo -e "${BLUE}STEP 8: Run Database Migration${NC}"
echo "=================================="
echo ""
echo "After deployment, run the migration to create tables:"
echo ""
echo "Option 1: Run via Railway CLI"
echo "  railway run 'cd backend && alembic upgrade head'"
echo ""
echo "Option 2: Connect via psql"
echo "  Get connection string from Railway → PostgreSQL → Connect"
echo "  Run: psql <CONNECTION_STRING> -f backend/migrations/001_add_auto_execution_fields.sql"
echo ""

read -p "Press Enter after running migration..."

echo ""

# ============================================================================
# STEP 9: Verification
# ============================================================================
echo -e "${BLUE}STEP 9: Verify Deployment${NC}"
echo "=================================="
echo ""

# Get Railway deployment URL
RAILWAY_URL=$(railway domain 2>/dev/null || echo "https://your-railway-domain.railway.app")

echo "Your API endpoints:"
echo "  Health Check: $RAILWAY_URL/health"
echo "  API Docs: $RAILWAY_URL/docs"
echo "  OpenAPI Schema: $RAILWAY_URL/openapi.json"
echo ""

echo "Test the API:"
echo "  curl $RAILWAY_URL/health"
echo ""

# ============================================================================
# STEP 10: Summary
# ============================================================================
echo -e "${BLUE}STEP 10: Deployment Summary${NC}"
echo "=================================="
echo ""
echo -e "${GREEN}✓ Backend Deployment Configured${NC}"
echo ""
echo "Next steps:"
echo "  1. Push changes to GitHub: git push origin main"
echo "  2. Railway will auto-deploy (takes 2-5 minutes)"
echo "  3. Monitor deployment in Railway dashboard"
echo "  4. Run database migrations"
echo "  5. Test API endpoints"
echo ""

echo "Live System URLs:"
echo "  Frontend: https://frontend-ivbkhvgqd-nish-markets.vercel.app"
echo "  Backend API: $RAILWAY_URL"
echo ""

echo -e "${GREEN}=========================================="
echo "BACKEND DEPLOYMENT READY! 🚀"
echo "==========================================${NC}"
echo ""
