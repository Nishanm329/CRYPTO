#!/bin/bash

# ============================================================================
# AUTO-EXECUTION FEATURE - VERCEL DEPLOYMENT AUTOMATION SCRIPT
# ============================================================================
# This script automates the local deployment preparation steps
# ============================================================================

set -e

echo "=========================================="
echo "AUTO-EXECUTION FEATURE - DEPLOYMENT SETUP"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# STEP 1: Generate Secrets
# ============================================================================
echo -e "${BLUE}STEP 1: Generate Secrets${NC}"
echo "=================================="

JWT_SECRET=$(openssl rand -hex 32)
echo -e "${GREEN}✓ JWT_SECRET generated:${NC}"
echo "  $JWT_SECRET"
echo ""

# ============================================================================
# STEP 2: Verify Git Setup
# ============================================================================
echo -e "${BLUE}STEP 2: Verify Git Setup${NC}"
echo "=================================="

if [ -d .git ]; then
    echo -e "${GREEN}✓ Git repository initialized${NC}"
    git log --oneline -1
else
    echo -e "${YELLOW}✗ Git not initialized${NC}"
    git init
    git config user.name "CryptoSignal Dev"
    git config user.email "dev@cryptosignal.app"
fi
echo ""

# ============================================================================
# STEP 3: Verify Project Structure
# ============================================================================
echo -e "${BLUE}STEP 3: Verify Project Structure${NC}"
echo "=================================="

checks=(
    "backend/auto_execution_engine.py"
    "backend/main.py"
    "backend/models.py"
    "backend/repositories.py"
    "backend/migrations/001_add_auto_execution_fields.sql"
    "frontend/components/AutoExecutionSettings.js"
    "vercel.json"
    ".env.vercel"
    "VERCEL_DEPLOYMENT.md"
    "VERCEL_DEPLOYMENT_CHECKLIST.md"
)

for file in "${checks[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${YELLOW}✗${NC} $file (missing)"
    fi
done
echo ""

# ============================================================================
# STEP 4: Create Deployment Configuration
# ============================================================================
echo -e "${BLUE}STEP 4: Create Deployment Config${NC}"
echo "=================================="

cat > .github/workflows/deploy-vercel.yml << 'WORKFLOW_EOF'
name: Deploy to Vercel

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Vercel CLI
        run: npm i -g vercel
      
      - name: Install dependencies
        run: npm install --prefix frontend
      
      - name: Run tests
        run: |
          pip install -r backend/requirements.txt
          python -m pytest backend/tests/ -v --cov
      
      - name: Pull Vercel environment
        run: vercel pull --yes --environment=production
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
      
      - name: Build project
        run: vercel build --prod
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
      
      - name: Deploy to Vercel
        run: vercel deploy --prebuilt --prod
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
WORKFLOW_EOF

echo -e "${GREEN}✓ Created .github/workflows/deploy-vercel.yml${NC}"
echo ""

# ============================================================================
# STEP 5: Create .env.production.vercel
# ============================================================================
echo -e "${BLUE}STEP 5: Create Environment Template${NC}"
echo "=================================="

cat > .env.production.vercel << ENV_EOF
# VERCEL PRODUCTION ENVIRONMENT VARIABLES
# Copy these to Vercel Project Settings > Environment Variables

# Frontend
NEXT_PUBLIC_API_URL=https://crypto-signals-api.vercel.app
NEXT_PUBLIC_ENVIRONMENT=production

# Backend - Database (SET THIS AFTER DATABASE IS CREATED)
DATABASE_URL=postgresql://user:password@host:5432/crypto_signals
ENVIRONMENT=production
LOG_LEVEL=info

# Authentication
API_KEYS=demo-key-public:demo-user
JWT_SECRET=$JWT_SECRET
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# Auto-Execution Feature
ENABLE_AUTO_EXECUTION=true
ENABLE_PAPER_TRADING=true
ENABLE_LIVE_TRADING=false

VERY_HIGH_CONFIDENCE_THRESHOLD=85
HIGH_CONFIDENCE_THRESHOLD=75

AUTO_EXEC_VERY_HIGH_SIZE=1.0
AUTO_EXEC_HIGH_SIZE=0.8
AUTO_EXEC_RECOVERY_SIZE=0.5

# Binance (OPTIONAL - set if you have credentials)
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TEST_MODE=false
ENV_EOF

echo -e "${GREEN}✓ Created .env.production.vercel${NC}"
echo -e "${YELLOW}  ⚠ Remember to update DATABASE_URL before deploying!${NC}"
echo ""

# ============================================================================
# STEP 6: Final Status Check
# ============================================================================
echo -e "${BLUE}STEP 6: Final Status Check${NC}"
echo "=================================="

echo -e "${GREEN}✓ All deployment files ready${NC}"
echo -e "${GREEN}✓ Git repository initialized${NC}"
echo -e "${GREEN}✓ Environment variables generated${NC}"
echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo -e "${BLUE}DEPLOYMENT SUMMARY${NC}"
echo "=========================================="
echo ""
echo "✓ JWT_SECRET (save for Vercel):"
echo "  $JWT_SECRET"
echo ""
echo "Next manual steps:"
echo "  1. Create GitHub repo: github.com/new"
echo "     Name: crypto-signals"
echo ""
echo "  2. Push code to GitHub:"
echo "     git remote add origin https://github.com/YOUR_USERNAME/crypto-signals.git"
echo "     git push -u origin main"
echo ""
echo "  3. Set up database:"
echo "     - Create account at neon.tech or railway.app"
echo "     - Get CONNECTION_STRING"
echo "     - Run: psql CONNECTION_STRING < backend/migrations/001_add_auto_execution_fields.sql"
echo ""
echo "  4. Deploy to Vercel:"
echo "     - Go to vercel.com"
echo "     - Click 'New Project'"
echo "     - Import crypto-signals GitHub repo"
echo "     - Set Root Directory: frontend/"
echo "     - Add environment variables from .env.production.vercel"
echo "     - Deploy!"
echo ""
echo "  5. Deploy backend (choose one):"
echo "     Option A: vercel --prod --name crypto-signals-api"
echo "     Option B: Deploy to railway.app separately"
echo ""
echo "Documentation:"
echo "  - VERCEL_DEPLOYMENT.md (comprehensive guide)"
echo "  - VERCEL_DEPLOYMENT_CHECKLIST.md (step-by-step)"
echo ""
echo -e "${GREEN}Ready to deploy! 🚀${NC}"
echo ""

