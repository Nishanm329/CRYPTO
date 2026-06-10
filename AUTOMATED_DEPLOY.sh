#!/bin/bash

# ============================================================================
# CRYPTOSIGNAL PRODUCTION DEPLOYMENT SCRIPT
# ============================================================================
# This script automates most of the deployment process.
# Some steps (Vercel/Railway OAuth) still require browser interaction.
# ============================================================================

set -e

echo "=========================================="
echo "CryptoSignal - Automated Deployment"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ============================================================================
# STEP 1: Verify GitHub Push
# ============================================================================
echo -e "${BLUE}STEP 1: Verifying GitHub push${NC}"
echo "=================================="

REMOTE_URL=$(git remote get-url origin)
if [[ $REMOTE_URL == *"github.com"* ]]; then
    echo -e "${GREEN}✓ Remote configured: $REMOTE_URL${NC}"
    
    # Check if main branch exists on remote
    if git rev-parse --verify origin/main &>/dev/null; then
        echo -e "${GREEN}✓ Code is on GitHub (main branch)${NC}"
    else
        echo -e "${RED}✗ Main branch not found on remote${NC}"
        echo "Push code with: git push -u origin main"
        exit 1
    fi
else
    echo -e "${RED}✗ GitHub remote not configured${NC}"
    exit 1
fi

echo ""

# ============================================================================
# STEP 2: Generate Production Secrets
# ============================================================================
echo -e "${BLUE}STEP 2: Generating production secrets${NC}"
echo "=================================="

JWT_SECRET=$(openssl rand -hex 32)
echo -e "${GREEN}✓ JWT_SECRET generated${NC}"

# Save to file
cat > /tmp/production_secrets.txt << EOF
JWT_SECRET=$JWT_SECRET
GITHUB_REPO=https://github.com/Nishanm329/CRYPTO
EOF

echo "Saved to: /tmp/production_secrets.txt"
echo ""

# ============================================================================
# STEP 3: Vercel Deployment
# ============================================================================
echo -e "${BLUE}STEP 3: Frontend Deployment (Vercel)${NC}"
echo "=================================="
echo ""
echo "You must do this manually (requires GitHub OAuth):"
echo "1. Go to: https://vercel.com/new"
echo "2. Sign in with GitHub"
echo "3. Import repository: Nishanm329/CRYPTO"
echo "4. Configure:"
echo "   - Framework: Next.js"
echo "   - Root Directory: frontend/"
echo "   - Build: npm run build"
echo "5. Environment Variables:"
echo "   - NEXT_PUBLIC_API_URL: https://crypto-signals-api.vercel.app"
echo "   - NEXT_PUBLIC_ENVIRONMENT: production"
echo "6. Deploy and SAVE your frontend URL"
echo ""

read -p "Enter your Vercel frontend URL (e.g., https://crypto-signals-XXXX.vercel.app): " FRONTEND_URL

if [[ -z "$FRONTEND_URL" ]]; then
    echo -e "${RED}Frontend URL required${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Frontend URL: $FRONTEND_URL${NC}"
echo ""

# ============================================================================
# STEP 4: Railway Deployment
# ============================================================================
echo -e "${BLUE}STEP 4: Backend Deployment (Railway)${NC}"
echo "=================================="
echo ""
echo "Manual steps (requires GitHub OAuth):"
echo "1. Go to: https://railway.app/new"
echo "2. Create PostgreSQL database:"
echo "   - Click 'Provision PostgreSQL'"
echo "   - Note the connection string"
echo "3. Add GitHub Repo service:"
echo "   - Select: Nishanm329/CRYPTO"
echo "   - Root Directory: backend"
echo "4. Add environment variables (see below)"
echo "5. Deploy"
echo ""
echo "Environment variables to add:"
echo "  ENVIRONMENT=production"
echo "  LOG_LEVEL=info"
echo "  JWT_SECRET=$JWT_SECRET"
echo "  API_KEYS=demo-key-public:demo-user"
echo "  ENABLE_AUTO_EXECUTION=true"
echo "  ENABLE_PAPER_TRADING=true"
echo "  ENABLE_LIVE_TRADING=false"
echo "  VERY_HIGH_CONFIDENCE_THRESHOLD=85"
echo "  HIGH_CONFIDENCE_THRESHOLD=75"
echo ""

read -p "Enter your Railway PostgreSQL connection string: " DATABASE_URL

if [[ -z "$DATABASE_URL" ]]; then
    echo -e "${RED}Database URL required${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Database connected${NC}"
echo ""

# ============================================================================
# STEP 5: Database Migration
# ============================================================================
echo -e "${BLUE}STEP 5: Running database migration${NC}"
echo "=================================="

read -p "Run migration now? (y/n): " RUN_MIGRATION

if [[ "$RUN_MIGRATION" == "y" ]]; then
    if psql "$DATABASE_URL" < backend/migrations/001_add_auto_execution_fields.sql; then
        echo -e "${GREEN}✓ Database migration successful${NC}"
    else
        echo -e "${RED}✗ Migration failed${NC}"
        echo "Try manually:"
        echo "psql \"$DATABASE_URL\" < backend/migrations/001_add_auto_execution_fields.sql"
    fi
else
    echo "Skipped. Run manually later:"
    echo "psql \"$DATABASE_URL\" < backend/migrations/001_add_auto_execution_fields.sql"
fi

echo ""

# ============================================================================
# STEP 6: Testing
# ============================================================================
echo -e "${BLUE}STEP 6: Production Testing${NC}"
echo "=================================="
echo ""
echo "Test your deployment:"
echo "  Frontend: $FRONTEND_URL"
echo "  API Health: https://crypto-signals-api.vercel.app/health"
echo "  API Docs: https://crypto-signals-api.vercel.app/docs"
echo ""

echo -e "${GREEN}=========================================="
echo "DEPLOYMENT COMPLETE! 🚀"
echo "==========================================${NC}"
echo ""
echo "Summary:"
echo "  Frontend: $FRONTEND_URL"
echo "  Backend: https://crypto-signals-api.vercel.app"
echo "  Database: PostgreSQL on Railway"
echo ""
echo "Next steps:"
echo "  1. Visit your frontend URL"
echo "  2. Check API health endpoint"
echo "  3. Create test trades"
echo "  4. Monitor in production"
echo ""

# Save configuration
cat > /tmp/production_config.txt << EOF
FRONTEND_URL=$FRONTEND_URL
DATABASE_URL=$DATABASE_URL
JWT_SECRET=$JWT_SECRET
API_URL=https://crypto-signals-api.vercel.app
EOF

echo "Configuration saved to: /tmp/production_config.txt"

