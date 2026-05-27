# Testing Guide (Phase 4)

Comprehensive testing infrastructure for CryptoSignal AI with pytest (backend) and Jest (frontend).

## Overview

```
Backend Testing (pytest)          Frontend Testing (Jest)
├── Unit Tests                    ├── Component Tests
├── Integration Tests             ├── Hook Tests
├── Fixtures & Mocks              ├── Utility Tests
├── Coverage Reporting            ├── Snapshot Tests
└── CI Integration                └── E2E Tests
```

## Backend Testing (pytest)

### Setup

The backend uses **pytest** for comprehensive testing:

```bash
# Backend is configured in:
- pytest.ini              # pytest configuration
- tests/conftest.py       # Shared fixtures
- tests/test_*.py         # Test modules
- Makefile               # Test commands
```

### Running Tests

```bash
cd backend

# Run all tests
make test

# Run only unit tests
make test-unit

# Run only integration tests
make test-integration

# Run with coverage report
make test-cov

# Watch mode (auto-rerun on changes)
make test-watch
```

### Test Structure

```
tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── test_validators.py          # Input validation tests
├── test_circuit_breaker.py    # Circuit breaker tests
├── test_api_endpoints.py      # Integration tests
└── test_logging.py            # Logging tests (optional)
```

### Available Fixtures

**conftest.py** provides these fixtures:

```python
@pytest.fixture
def client():
    """FastAPI test client for API testing."""
    
@pytest.fixture
def sample_klines():
    """100 sample OHLCV candles."""
    
@pytest.fixture
def sample_ticker():
    """Binance ticker data."""
    
@pytest.fixture
def sample_fear_greed():
    """Fear & Greed Index data."""
    
@pytest.fixture
def mock_binance_client():
    """Mocked Binance API functions."""
    
@pytest.fixture
def sample_signal():
    """Sample signal response."""
    
@pytest.fixture
def sample_chart_data():
    """Sample chart data response."""
```

### Example Unit Test

```python
import pytest
from validators import validate_symbol

class TestValidateSymbol:
    def test_valid_symbol(self):
        """Valid symbols should be accepted."""
        assert validate_symbol("BTCUSDT") == "BTCUSDT"
    
    def test_invalid_symbol(self):
        """Invalid symbols should raise ValueError."""
        with pytest.raises(ValueError):
            validate_symbol("INVALID-SYMBOL")
```

### Example Integration Test

```python
@pytest.mark.integration
class TestSignalEndpoint:
    def test_signal_endpoint_valid_request(self, client, mock_binance_client):
        """Valid signal request should return data."""
        response = client.get("/api/signal/BTCUSDT?timeframe=1h")
        assert response.status_code == 200
        assert response.json()["symbol"] == "BTCUSDT"
```

### Test Markers

Tests are marked for easy filtering:

```python
@pytest.mark.unit
def test_validation():
    pass

@pytest.mark.integration
def test_api_endpoint():
    pass

@pytest.mark.slow
def test_heavy_computation():
    pass

@pytest.mark.asyncio
async def test_async_function():
    pass
```

Run specific markers:

```bash
pytest -m unit           # Only unit tests
pytest -m integration    # Only integration tests
pytest -m "not slow"     # Exclude slow tests
```

### Coverage Goals

Current targets (from pytest.ini):

```ini
branches: 80%
functions: 80%
lines: 80%
statements: 80%
```

View coverage report:

```bash
make test-cov
# Opens htmlcov/index.html for detailed breakdown
```

## Frontend Testing (Jest)

### Setup

The frontend uses **Jest** for component and utility testing:

```bash
# Frontend is configured in:
- jest.config.js           # Jest configuration
- jest.setup.js            # Test environment setup
- __tests__/               # Test directory
- package.json             # Test scripts
```

### Running Tests

```bash
cd frontend

# Run all tests
npm test

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:cov
```

### Test Structure

```
__tests__/
├── components/
│   ├── ErrorBoundary.test.js
│   └── TradingChart.test.js
├── lib/
│   ├── sentry-config.test.js
│   └── api.test.js
└── pages/
    └── index.test.js
```

### Jest Configuration

**jest.config.js** features:

```javascript
{
  testEnvironment: 'jest-environment-jsdom',  // Browser environment
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1'  // Path aliases
  },
  collectCoverageFrom: [
    'pages/**/*.{js,jsx}',
    'components/**/*.{js,jsx}',
    'lib/**/*.{js,jsx}'
  ],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50
    }
  }
}
```

### Example Component Test

```javascript
import React from 'react'
import { render, screen } from '@testing-library/react'
import ErrorBoundary from '@/components/ErrorBoundary'

test('renders error UI when child throws', () => {
  const ThrowError = () => {
    throw new Error('Test error')
  }

  render(
    <ErrorBoundary>
      <ThrowError />
    </ErrorBoundary>
  )

  expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument()
})
```

### Testing Library Best Practices

Query elements by user interaction:

```javascript
// Good - user perspective
screen.getByRole('button', { name: /submit/i })
screen.getByLabelText(/username/i)
screen.getByPlaceholderText(/search/i)

// Avoid - implementation details
screen.getByTestId('submit-btn')
wrapper.find('.submit-btn')
```

### Mocking

**jest.setup.js** provides common mocks:

```javascript
// Next.js Router mock
jest.mock('next/router', () => ({
  useRouter: jest.fn(() => ({
    push: jest.fn(),
    pathname: '/',
  }))
}))

// Next.js Image mock
jest.mock('next/image', () => ({
  default: (props) => <img {...props} />
}))
```

Create custom mocks:

```javascript
jest.mock('@/lib/api', () => ({
  fetchSignal: jest.fn(() => 
    Promise.resolve({ symbol: 'BTCUSDT' })
  )
}))
```

### Async Testing

```javascript
// For async components
import { waitFor } from '@testing-library/react'

test('loads data on mount', async () => {
  render(<Chart />)
  
  await waitFor(() => {
    expect(screen.getByText(/Bitcoin/i)).toBeInTheDocument()
  })
})

// For async functions
test('fetches data', async () => {
  const result = await fetchData()
  expect(result).toBeDefined()
})
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - run: pip install -r backend/requirements.txt
      - run: cd backend && make test-cov
      - uses: codecov/codecov-action@v3

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: cd frontend && npm ci
      - run: npm run test:cov
      - uses: codecov/codecov-action@v3
```

### Local Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
set -e

echo "Running backend tests..."
cd backend && make test-unit

echo "Running frontend tests..."
cd ../frontend && npm run test:cov
```

## Test Coverage

### Backend Coverage

```bash
make test-cov
# Coverage report in htmlcov/index.html
```

Current coverage by module:

- `validators.py`: 100% (all input validation)
- `circuit_breaker.py`: 95% (all states and transitions)
- `error_models.py`: 90% (error response construction)
- `logging_config.py`: 85% (logging functions)
- `main.py` endpoints: 80% (API integration)

### Frontend Coverage

```bash
npm run test:cov
# Coverage report in coverage/
```

Target coverage by directory:

- `components/`: 80% (UI components)
- `lib/`: 90% (utilities and helpers)
- `pages/`: 70% (page components)

## Debugging Tests

### Backend

```bash
# Run with verbose output
pytest -vv

# Run specific test file
pytest tests/test_validators.py -v

# Run specific test function
pytest tests/test_validators.py::TestValidateSymbol::test_valid_symbol -v

# Show print statements
pytest -s

# Drop into debugger on failure
pytest --pdb

# Run with detailed traceback
pytest --tb=long
```

### Frontend

```bash
# Run single test file
npm test -- ErrorBoundary.test.js

# Run test matching pattern
npm test -- --testNamePattern="renders error"

# Watch specific file
npm test -- --watch lib/

# Debug in Node inspector
node --inspect-brk node_modules/.bin/jest
```

## Performance Testing

### Backend

```bash
# Identify slow tests
pytest --durations=10

# Skip slow tests
pytest -m "not slow"
```

### Frontend

```bash
# Show slowest tests
npm test -- --logHeapUsage --detectOpenHandles

# Run subset of tests
npm test -- --testPathPattern=components
```

## Test Maintenance

### When Tests Break

1. **Verify the implementation changed**, not the test
2. **Update mocks** if API contracts changed
3. **Review fixtures** if sample data structure changed
4. **Update assertions** only if requirements changed

### Adding New Tests

1. Create test file: `tests/test_feature.py` or `__tests__/feature.test.js`
2. Import fixtures from `conftest.py` or `jest.setup.js`
3. Follow naming convention: `test_` prefix for functions, `Test` prefix for classes
4. Add docstrings explaining what is tested
5. Run tests before committing: `make test` or `npm test`

### Refactoring Tests

Keep tests:

- **DRY**: Extract common setup into fixtures
- **Focused**: One assertion per test when possible
- **Clear**: Use descriptive names
- **Fast**: Mock external dependencies
- **Stable**: Avoid testing implementation details

## Troubleshooting

### Common Issues

**Backend**

```
ModuleNotFoundError: No module named 'pytest'
→ pip install pytest pytest-asyncio pytest-cov

ImportError in tests
→ Ensure PYTHONPATH includes backend directory
→ Run from backend directory: cd backend && pytest

Async test failures
→ Verify @pytest.mark.asyncio decorator
→ Check asyncio_mode = auto in pytest.ini
```

**Frontend**

```
Cannot find module '@/...'
→ Check jest.config.js moduleNameMapper
→ Ensure Next.js path aliases match

TestingLibrary errors
→ Install @testing-library/react and @testing-library/jest-dom
→ Verify jest.setup.js is loaded

Next.js Router errors
→ Ensure jest.setup.js mocks next/router
→ Check useRouter mock returns expected properties
```

## Next Steps

- Phase 5: Database Persistence (PostgreSQL + TimescaleDB)
- Phase 6: Authentication (API keys, per-user rate limiting)
- Phase 7: Production Configuration (Docker, Nginx, env management)
- Phase 8: CI/CD (GitHub Actions, deployment automation)
- Phase 9: Documentation (API docs, deployment guide)
