#!/bin/bash

# ============================================================================
# PUSH CODE TO GITHUB
# ============================================================================

set -e

echo "=========================================="
echo "PUSHING CODE TO GITHUB"
echo "=========================================="
echo ""

# Check if git is configured
if ! git config user.email > /dev/null 2>&1; then
    echo "Configuring Git..."
    git config user.name "CryptoSignal Dev"
    git config user.email "dev@cryptosignal.app"
fi

# Get the repository URL
read -p "Enter your GitHub repository URL (e.g., https://github.com/username/repo): " REPO_URL

# Remove any existing remote
git remote remove origin 2>/dev/null || true

# Add the remote
git remote add origin "$REPO_URL"

# Set branch to main
git branch -M main

# Push to GitHub
echo ""
echo "Pushing code to GitHub..."
echo "You may be asked to authenticate..."
echo ""

git push -u origin main --force

echo ""
echo "=========================================="
echo "✓ Code pushed successfully!"
echo "=========================================="
echo ""
echo "Your repository:"
echo "  $REPO_URL"
echo ""
echo "Next step:"
echo "  1. Go to https://vercel.com/new"
echo "  2. Select your repository"
echo "  3. Deploy!"
echo ""
