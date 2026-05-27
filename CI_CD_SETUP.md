# CI/CD Pipeline Setup Guide

Comprehensive guide for setting up GitHub Actions workflows for testing and deployment.

## Overview

```
Push Code
    ↓
GitHub Actions (test.yml)
    ├─ Backend: Python tests, linting, type checking
    ├─ Frontend: JavaScript tests, linting
    └─ Integration: Database + API tests
    ↓
If ALL tests pass:
    ↓ (on main branch)
    Build Docker images
    ↓
    Deploy to Staging
    ↓
    Smoke tests
    ↓ (if version tag created)
    Deploy to Production
```

## Prerequisites

- GitHub repository with CI/CD enabled
- Staging and production servers
- Docker registry (GitHub Container Registry by default)
- Slack workspace (optional, for notifications)

## Setup Steps

### 1. GitHub Secrets Configuration

Go to **Settings → Secrets and variables → Actions** and add:

#### Staging Secrets

```
STAGING_HOST          = staging.example.com
STAGING_USER          = deploy
STAGING_SSH_KEY       = (private SSH key)
STAGING_DB_HOST       = postgres.staging.internal
STAGING_DB_PASSWORD   = (database password)
STAGING_API_KEYS      = key1:user1,key2:user2
STAGING_SENTRY_DSN    = https://xxx@sentry.io/yyy
```

#### Production Secrets

```
PROD_HOST             = prod.example.com
PROD_USER             = deploy
PROD_SSH_KEY          = (private SSH key)
PROD_DB_HOST          = postgres.prod.internal
PROD_DB_PASSWORD      = (database password)
PROD_API_KEYS         = key1:user1,key2:user2
PROD_SENTRY_DSN       = https://xxx@sentry.io/yyy
PROD_CORS_ORIGINS     = https://cryptosignal.com
```

#### Frontend Build Secrets

```
NEXT_PUBLIC_API_URL   = https://api.cryptosignal.com
NEXT_PUBLIC_API_KEY   = (production API key)
```

#### Notifications

```
SLACK_WEBHOOK_URL     = https://hooks.slack.com/services/XXX/YYY/ZZZ
```

### 2. SSH Key Setup

Generate SSH key for deployments:

```bash
# Generate key (no passphrase for CI/CD)
ssh-keygen -t ed25519 -f deploy_key -N ""

# Add public key to server
cat deploy_key.pub >> ~/.ssh/authorized_keys

# Add private key to GitHub Secrets
cat deploy_key | base64  # Copy output to STAGING_SSH_KEY secret
```

### 3. GitHub Environments Setup

Create environments for staging and production:

1. Go to **Settings → Environments**
2. Create "staging" environment
3. Create "production" environment
4. For production: Enable "Require reviewers" (optional)
5. Add environment-specific secrets for each

### 4. Workflow File Configuration

Both workflow files are already in `.github/workflows/`:

- `test.yml` — Runs on all pushes and pull requests
- `deploy.yml` — Runs on main branch push and version tags

## Workflow: test.yml

### Triggers

- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

### Jobs

#### Backend Tests
- Lint with flake8
- Type check with mypy
- Format check with Black
- Run pytest with coverage
- Upload to Codecov

#### Frontend Tests
- Lint with ESLint
- Format check with Prettier
- Run Jest tests with coverage
- Upload to Codecov

#### Integration Tests
- Run pytest marked as `@pytest.mark.integration`
- Test database + API together

### Expected Results

```
✅ Linting passed
✅ Type checking passed
✅ Format check passed
✅ Unit tests passed (95%+ coverage)
✅ Integration tests passed
✅ Coverage uploaded to Codecov
```

## Workflow: deploy.yml

### Triggers

- Push to `main` branch (deploys to staging)
- Tag push matching `v*` (deploys to production)

### Jobs

#### Build
- Checkout code
- Build Docker images
- Push to GitHub Container Registry
- Output image names for next jobs

#### Deploy to Staging
- SSH into staging server
- Pull latest code
- Update environment variables
- Run `docker-compose up -d`
- Run database migrations
- Verify with health checks

#### Smoke Tests (Staging)
- Test health endpoint
- Test API authentication
- Test chart endpoint
- Test sentiment endpoint

#### Deploy to Production
- Only on version tags (v1.0.0, v2.1.3, etc.)
- Requires "production" environment approval
- Creates GitHub Release
- Backup database before deploy
- Deploy with health checks
- 30-second timeout for service startup

## Code Quality Gates

### Pre-Commit Hooks

Before committing, install pre-commit hooks:

```bash
# Install pre-commit
pip install pre-commit

# Set up hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

Checks run automatically on every commit:
- ✅ Trailing whitespace
- ✅ End of file fixer
- ✅ Python formatting (Black)
- ✅ Import sorting (isort)
- ✅ Python linting (flake8)
- ✅ JavaScript formatting (Prettier)
- ✅ JavaScript linting (ESLint)
- ✅ YAML formatting
- ✅ Markdown linting
- ✅ Security checks

### GitHub Actions Checks

Run on every push/PR:
- ✅ Linting (flake8, ESLint)
- ✅ Type checking (mypy)
- ✅ Formatting (Black, Prettier)
- ✅ Unit tests (pytest, Jest)
- ✅ Integration tests
- ✅ Coverage requirements

Must pass before merging to main.

## Deployment Process

### Deploy to Staging

```bash
# Any push to main branch automatically deploys to staging
git push origin main

# GitHub Actions will:
# 1. Run all tests
# 2. Build Docker images
# 3. Deploy to staging server
# 4. Run smoke tests
# 5. Notify Slack on success/failure
```

### Deploy to Production

```bash
# Create a version tag to deploy to production
git tag v1.2.3
git push origin v1.2.3

# GitHub Actions will:
# 1. Run all tests
# 2. Build Docker images
# 3. Create GitHub Release
# 4. Wait for approval (if configured)
# 5. Deploy to production server
# 6. Backup database first
# 7. Run migrations
# 8. Health checks
# 9. Notify Slack
```

### Approval Workflow (Optional)

For production deployments, require manual approval:

1. Go to **Settings → Environments → production**
2. Enable "Required reviewers"
3. Add team members as reviewers

When a production deployment is queued, reviewers will be notified to approve/deny.

## Monitoring Deployments

### View Workflow Runs

1. Go to **Actions** tab in GitHub
2. Select workflow (test.yml or deploy.yml)
3. Click run to view logs

### Check Deployment Status

```bash
# SSH to server
ssh deploy@staging.example.com

# View logs
docker-compose -f docker-compose.prod.yml logs -f backend

# Check status
docker-compose -f docker-compose.prod.yml ps
```

### Slack Notifications

Receive notifications for:
- ✅ Test passes
- ❌ Test failures
- 🚀 Staging deployment success
- ❌ Staging deployment failure
- 🚀 Production deployment success
- ❌ Production deployment failure

## Rollback Procedure

If production deployment fails:

```bash
# 1. SSH to production server
ssh deploy@prod.example.com

# 2. Check recent git tags
git log --oneline --graph --decorate

# 3. Revert to previous version
git checkout v1.2.2
docker-compose -f docker-compose.prod.yml up -d

# 4. Restore database from backup (if needed)
gunzip -c /backups/db-TIMESTAMP.sql.gz | \
  docker-compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres crypto_signals

# 5. Verify
curl https://cryptosignal.com/health
```

## Performance Optimization

### Caching

GitHub Actions caches:
- Docker layers (via `docker/setup-buildx-action`)
- Python dependencies (via `actions/setup-python` with cache)
- Node modules (via `actions/setup-node` with cache)

Cache speeds up builds 5-10x.

### Parallel Jobs

Jobs run in parallel:
- Backend tests (10-15 minutes)
- Frontend tests (5-10 minutes)
- Integration tests (15-20 minutes)

Total: ~20 minutes (vs ~45 if sequential)

### Conditional Deployment

Production only deploys on version tags:
```yaml
if: startsWith(github.ref, 'refs/tags/v')
```

Prevents accidental production deploys on main branch.

## Common Issues

### "SSH: Permission denied"

**Problem**: SSH key not in authorized_keys

**Solution**:
```bash
# On server
cat ~/.ssh/authorized_keys | grep "deploy_key"

# If missing
cat deploy_key.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### "Docker image not found"

**Problem**: Push to registry failed

**Solution**:
```bash
# Check GITHUB_TOKEN has packages:write permission
# In workflow, update login step:
- uses: docker/login-action@v2
  with:
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

### "Database migration failed"

**Problem**: Schema migration conflicts

**Solution**:
```bash
# Check alembic status
docker-compose -f docker-compose.prod.yml exec backend alembic current

# Rollback and retry
docker-compose -f docker-compose.prod.yml exec backend alembic downgrade -1
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### "Tests pass locally but fail in CI"

**Problem**: Environment differences

**Solution**:
- Check environment variables in workflow
- Verify database is accessible
- Check Python/Node versions match locally

## Best Practices

✅ Run tests before pushing
```bash
pre-commit run --all-files
pytest
npm test
```

✅ Use semantic versioning for releases
```bash
git tag v1.2.3  # Major.Minor.Patch
```

✅ Write descriptive commit messages
```bash
git commit -m "feat: add signal persistence to database"
```

✅ Review test results before deploying
- Check Codecov coverage
- Review failed tests
- Verify no regressions

✅ Monitor production after deployment
- Check logs for errors
- Monitor API latency
- Check error rate in Sentry

## Scheduled Tasks (Optional)

For nightly/weekly tasks, add to workflow:

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

Example uses:
- Nightly database backups
- Weekly security scans
- Monthly dependency updates

## GitHub Protection Rules

Configure branch protection for main:

1. Go to **Settings → Branches**
2. Add rule for `main` branch
3. Enable:
   - "Require a pull request before merging"
   - "Require status checks to pass" (select all workflows)
   - "Require branches to be up to date"
   - "Include administrators" (optional)

This ensures all code is tested before merging.

## Next Steps

- Phase 9: Documentation (API docs, developer guide)
- Monitoring setup (Prometheus, Grafana)
- Performance tuning (caching, CDN)
- Security hardening (secrets rotation, audit logs)
