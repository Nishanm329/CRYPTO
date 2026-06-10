#!/bin/bash

# ============================================================================
# RENDER.COM BACKEND DEPLOYMENT - QUICK START
# ============================================================================
# This script guides you through deploying to Render.com
# Much faster than Railway - takes ~10 minutes total
# ============================================================================

set -e

echo "=========================================="
echo "CRYPTO SIGNALS - RENDER.COM DEPLOYMENT"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ============================================================================
# STEP 1: Pre-flight Checks
# ============================================================================
echo -e "${BLUE}STEP 1: Pre-flight Checks${NC}"
echo "=================================="

# Check if requirements.txt exists
if [ ! -f "backend/requirements.txt" ]; then
    echo -e "${RED}✗ backend/requirements.txt not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ requirements.txt found${NC}"

# Check if main.py exists
if [ ! -f "backend/main.py" ]; then
    echo -e "${RED}✗ backend/main.py not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ main.py found${NC}"

# Check if Procfile exists
if [ ! -f "Procfile" ]; then
    echo -e "${YELLOW}⚠ No Procfile found, creating one...${NC}"
    cat > Procfile << 'EOF'
web: cd backend && python -m uvicorn main:app --host 0.0.0.0 --port $PORT
EOF
    echo -e "${GREEN}✓ Created Procfile${NC}"
fi

echo ""
echo -e "${GREEN}All files ready for deployment!${NC}"
echo ""

# ============================================================================
# STEP 2: GitHub Setup Verification
# ============================================================================
echo -e "${BLUE}STEP 2: GitHub Setup Verification${NC}"
echo "=================================="

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo -e "${RED}✗ Not a git repository!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Git repository found${NC}"

# Check git remote
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$REMOTE_URL" == *"CRYPTO"* ]] || [[ "$REMOTE_URL" == *"crypto"* ]]; then
    echo -e "${GREEN}✓ GitHub remote: $REMOTE_URL${NC}"
else
    echo -e "${YELLOW}⚠ Could not verify GitHub remote${NC}"
fi

echo ""

# ============================================================================
# STEP 3: Render.com Account Setup
# ============================================================================
echo -e "${BLUE}STEP 3: Render.com Account Setup${NC}"
echo "=================================="
echo ""
echo "1. Go to: https://render.com"
echo "2. Click 'Sign up'"
echo "3. Use GitHub to sign up (recommended)"
echo "4. Authorize Render to access your GitHub repos"
echo ""
read -p "Have you created a Render.com account? (y/n): " RENDER_ACCOUNT

if [ "$RENDER_ACCOUNT" != "y" ]; then
    echo ""
    echo "Please create a Render.com account first at https://render.com"
    echo "Then run this script again."
    exit 0
fi

echo ""

# ============================================================================
# STEP 4: Create Web Service on Render
# ============================================================================
echo -e "${BLUE}STEP 4: Create Web Service on Render${NC}"
echo "=================================="
echo ""
echo "Now you'll create the deployment on Render.com:"
echo ""
echo "1. Go to: https://dashboard.render.com"
echo "2. Click 'New +' (top right)"
echo "3. Select 'Web Service'"
echo "4. When prompted, search for 'CRYPTO' repo"
echo "5. Select 'Nishanm329/CRYPTO' and click 'Connect'"
echo ""
echo "Then configure:"
echo "  • Name: crypto-signals-api"
echo "  • Region: Oregon (or closest to you)"
echo "  • Branch: main"
echo "  • Build Command: pip install -r requirements.txt"
echo "  • Start Command: cd backend && uvicorn main:app --host 0.0.0.0 --port \$PORT"
echo "  • Plan: Free"
echo ""
echo "Then add these Environment Variables:"
echo "  • ENVIRONMENT=production"
echo "  • LOG_LEVEL=INFO"
echo "  • CORS_ORIGINS=https://frontend-ivbkhvgqd-nish-markets.vercel.app"
echo "  • API_KEYS=demo-key-public:demo-user"
echo "  • RATE_LIMIT_SCAN=30"
echo "  • RATE_LIMIT_SIGNAL=60"
echo "  • RATE_LIMIT_CHART=60"
echo "  • RATE_LIMIT_MARKET=20"
echo "  • CIRCUIT_BREAKER_FAILURE_THRESHOLD=5"
echo "  • CIRCUIT_BREAKER_TIMEOUT=60"
echo "  • PROMETHEUS_ENABLED=true"
echo ""
echo "Finally, click 'Create Web Service'"
echo ""
read -p "Press Enter after clicking 'Create Web Service'..."

echo ""

# ============================================================================
# STEP 5: Wait for Deployment
# ============================================================================
echo -e "${BLUE}STEP 5: Wait for Deployment${NC}"
echo "=================================="
echo ""
echo "Render is now building your service..."
echo "This takes about 2-3 minutes."
echo ""
echo "You should see:"
echo "  • 'Building...' with progress bar"
echo "  • Then 'Build Successful' with green checkmark"
echo ""
echo "Watch the logs in the Render dashboard (Logs tab)"
echo ""
read -p "Press Enter after deployment completes (you see green checkmark)..."

echo ""

# ============================================================================
# STEP 6: Get Your API URL
# ============================================================================
echo -e "${BLUE}STEP 6: Get Your API URL${NC}"
echo "=================================="
echo ""
echo "In Render dashboard:"
echo "1. Click on your service"
echo "2. Go to 'Settings' tab"
echo "3. Look for 'Render Domain' section"
echo "4. Copy the URL (like: crypto-signals-api.onrender.com)"
echo ""

read -p "Enter your Render domain (e.g., crypto-signals-api.onrender.com): " RENDER_DOMAIN

if [ -z "$RENDER_DOMAIN" ]; then
    RENDER_DOMAIN="crypto-signals-api.onrender.com"
fi

RENDER_URL="https://$RENDER_DOMAIN"

echo ""
echo -e "${GREEN}Your API URL: $RENDER_URL${NC}"
echo ""

# ============================================================================
# STEP 7: Test the API
# ============================================================================
echo -e "${BLUE}STEP 7: Test the API${NC}"
echo "=================================="
echo ""
echo "Testing API health endpoint..."
echo ""

# Try to test the API
if command -v curl &> /dev/null; then
    echo "Running: curl $RENDER_URL/health"
    echo ""

    # Give Render a moment to be ready
    sleep 2

    if curl -s "$RENDER_URL/health" > /dev/null; then
        echo -e "${GREEN}✓ API is responding!${NC}"
        RESPONSE=$(curl -s "$RENDER_URL/health")
        echo "Response: $RESPONSE"
    else
        echo -e "${YELLOW}⚠ Could not reach API yet${NC}"
        echo "The service might still be starting up. Check back in a minute."
        echo "Go to: $RENDER_URL/health"
    fi
else
    echo "Manual test:"
    echo "Open in browser: $RENDER_URL/health"
    echo "Should see: {\"status\":\"ok\",\"environment\":\"production\"}"
fi

echo ""

# ============================================================================
# STEP 8: Update Frontend Configuration
# ============================================================================
echo -e "${BLUE}STEP 8: Update Frontend Configuration${NC}"
echo "=================================="
echo ""
echo "If your API URL is different from what frontend expects:"
echo ""
echo "1. Go to Vercel Dashboard"
echo "2. Click on 'crypto-signals' frontend project"
echo "3. Go to Settings → Environment Variables"
echo "4. Update NEXT_PUBLIC_API_URL to: $RENDER_URL"
echo "5. Vercel will auto-redeploy"
echo ""
read -p "Do you need to update frontend API URL? (y/n): " UPDATE_FRONTEND

if [ "$UPDATE_FRONTEND" == "y" ]; then
    echo ""
    echo "Go to: https://vercel.com/dashboard"
    echo "Update NEXT_PUBLIC_API_URL to: $RENDER_URL"
    echo ""
fi

echo ""

# ============================================================================
# STEP 9: Summary
# ============================================================================
echo -e "${GREEN}=========================================="
echo "BACKEND DEPLOYMENT COMPLETE! 🚀"
echo "==========================================${NC}"
echo ""
echo "Your System Status:"
echo "  Frontend: https://frontend-ivbkhvgqd-nish-markets.vercel.app"
echo "  Backend:  $RENDER_URL"
echo "  Health:   $RENDER_URL/health"
echo "  Docs:     $RENDER_URL/docs"
echo ""
echo "Next Steps:"
echo "1. Test the API: curl $RENDER_URL/health"
echo "2. Update frontend NEXT_PUBLIC_API_URL if needed"
echo "3. Open frontend and verify it connects to API"
echo "4. Check backend logs in Render dashboard"
echo ""
echo "Documentation:"
echo "  Full guide: ./RENDER_DEPLOYMENT.md"
echo ""
echo -e "${GREEN}Your backend is now LIVE! 🎉${NC}"
echo ""
