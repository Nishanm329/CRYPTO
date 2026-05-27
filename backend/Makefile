.PHONY: test test-unit test-integration test-cov test-watch lint

# Run all tests
test:
	pytest tests/ -v

# Run only unit tests
test-unit:
	pytest tests/ -v -m "not integration"

# Run only integration tests
test-integration:
	pytest tests/ -v -m integration

# Run tests with coverage report
test-cov:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing

# Watch tests (requires pytest-watch)
test-watch:
	ptw tests/ -- -v

# Lint code with flake8 (if installed)
lint:
	flake8 . --max-line-length=100 --exclude=tests,__pycache__

# Format code with black
format:
	black . --exclude=tests,__pycache__

# Run type checking with mypy
type-check:
	mypy . --ignore-missing-imports

# Run all checks
check: lint type-check test-cov

# Clean up temporary files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	rm -rf htmlcov
	rm -rf .coverage

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  test              - Run all tests"
	@echo "  test-unit         - Run only unit tests"
	@echo "  test-integration  - Run only integration tests"
	@echo "  test-cov          - Run tests with coverage report"
	@echo "  test-watch        - Run tests in watch mode"
	@echo "  lint              - Check code style"
	@echo "  format            - Format code with black"
	@echo "  type-check        - Run type checking"
	@echo "  check             - Run all checks"
	@echo "  clean             - Clean up temporary files"
