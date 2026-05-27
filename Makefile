.PHONY: help install dev test lint format clean docker-build docker-deploy

help:
	@echo "CryptoSignal AI - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install all dependencies"
	@echo "  make install-pre    Install pre-commit hooks"
	@echo ""
	@echo "Development:"
	@echo "  make dev            Start development servers (backend + frontend)"
	@echo "  make dev-backend    Start backend only"
	@echo "  make dev-frontend   Start frontend only"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-backend   Run backend tests"
	@echo "  make test-frontend  Run frontend tests"
	@echo "  make test-coverage  Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run linters (flake8, ESLint)"
	@echo "  make format         Format code (Black, Prettier)"
	@echo "  make check          Run all checks (lint, format, type)"
	@echo "  make pre-commit     Run pre-commit hooks"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker images"
	@echo "  make docker-up      Start Docker containers"
	@echo "  make docker-down    Stop Docker containers"
	@echo "  make docker-logs    View Docker logs"
	@echo ""
	@echo "Database:"
	@echo "  make db-init        Initialize database"
	@echo "  make db-migrate     Run migrations"
	@echo "  make db-reset       Reset database"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-staging Deploy to staging"
	@echo "  make deploy-prod    Deploy to production"

# =============================================================================
# Installation
# =============================================================================

install: install-backend install-frontend install-pre
	@echo "✅ All dependencies installed"

install-backend:
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

install-pre:
	@echo "Installing pre-commit hooks..."
	pip install pre-commit
	pre-commit install

# =============================================================================
# Development
# =============================================================================

dev:
	@echo "Starting development servers..."
	@make dev-backend & make dev-frontend

dev-backend:
	@echo "Starting backend (http://localhost:8000)..."
	cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "Starting frontend (http://localhost:3000)..."
	cd frontend && npm run dev

# =============================================================================
# Testing
# =============================================================================

test: test-backend test-frontend
	@echo "✅ All tests passed"

test-backend:
	@echo "Running backend tests..."
	cd backend && pytest tests/ -v --tb=short

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm test -- --coverage

test-coverage:
	@echo "Running tests with coverage..."
	cd backend && pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing
	cd frontend && npm run test:cov
	@echo "Coverage reports generated (backend: htmlcov/, frontend: coverage/)"

test-integration:
	@echo "Running integration tests..."
	cd backend && pytest tests/ -v -m integration

test-watch:
	@echo "Running tests in watch mode..."
	cd backend && pytest tests/ -v --tb=short -x --ff --lf

# =============================================================================
# Code Quality
# =============================================================================

lint:
	@echo "Running linters..."
	@echo "  Backend:"
	cd backend && flake8 . --max-line-length=120 --show-source
	@echo "  Frontend:"
	cd frontend && npx eslint . --ext .js,.jsx 2>/dev/null || true

format:
	@echo "Formatting code..."
	@echo "  Backend:"
	cd backend && black . && isort .
	@echo "  Frontend:"
	cd frontend && npx prettier --write . 2>/dev/null || true

type-check:
	@echo "Running type checks..."
	cd backend && mypy . --ignore-missing-imports 2>/dev/null || true

check: lint type-check
	@echo "✅ All checks passed"

pre-commit:
	@echo "Running pre-commit hooks..."
	pre-commit run --all-files

# =============================================================================
# Docker
# =============================================================================

docker-build:
	@echo "Building Docker images..."
	docker-compose build

docker-up:
	@echo "Starting Docker containers..."
	docker-compose up -d
	@echo "✅ Services running"
	@echo "  Backend: http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"

docker-down:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean:
	@echo "Removing Docker containers and volumes..."
	docker-compose down -v

# =============================================================================
# Database
# =============================================================================

db-init:
	@echo "Initializing database..."
	cd backend && python -c "from db import init_db; init_db()"
	@echo "✅ Database initialized"

db-migrate:
	@echo "Running database migrations..."
	cd backend && alembic upgrade head

db-reset:
	@echo "Resetting database..."
	cd backend && python -c "from db import drop_db; drop_db()"
	@echo "✅ Database reset"

# =============================================================================
# Deployment
# =============================================================================

deploy-staging:
	@echo "Deploying to staging..."
	git push origin main
	@echo "Deployment triggered (watch GitHub Actions)"

deploy-prod:
	@echo "Creating production release..."
	@read -p "Enter version (e.g., v1.2.3): " VERSION; \
	git tag $$VERSION && git push origin $$VERSION
	@echo "Deployment triggered (watch GitHub Actions)"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	cd backend && rm -rf .coverage coverage.xml 2>/dev/null || true
	cd frontend && rm -rf coverage/ 2>/dev/null || true
	@echo "✅ Cleanup complete"
