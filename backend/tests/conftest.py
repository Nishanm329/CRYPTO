"""
pytest configuration and shared fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_klines():
    """Sample OHLCV data (klines) for testing."""
    return [
        {
            "open_time": 1609459200000,
            "open": "29000.00",
            "high": "29500.00",
            "low": "28900.00",
            "close": "29300.00",
            "volume": "1234.5",
            "close_time": 1609545600000,
            "quote_asset_volume": "36000000.00",
            "number_of_trades": 5000,
            "taker_buy_base_asset_volume": "600.0",
            "taker_buy_quote_asset_volume": "17500000.00",
            "ignore": 0,
        }
        for i in range(100)
    ]


@pytest.fixture
def sample_ticker():
    """Sample ticker data from Binance."""
    return {
        "symbol": "BTCUSDT",
        "priceChange": "1200.00",
        "priceChangePercent": "4.3",
        "weightedAvgPrice": "29500.00",
        "prevClosePrice": "28100.00",
        "lastPrice": "29300.00",
        "lastQty": "0.5",
        "bidPrice": "29299.00",
        "bidQty": "2.3",
        "askPrice": "29300.00",
        "askQty": "1.2",
        "openPrice": "28100.00",
        "highPrice": "29800.00",
        "lowPrice": "28700.00",
        "volume": "50000.0",
        "quoteVolume": "1500000000.00",
        "openTime": 1609459200000,
        "closeTime": 1609545600000,
        "firstId": 123456,
        "lastId": 234567,
        "count": 111112,
    }


@pytest.fixture
def sample_fear_greed():
    """Sample Fear & Greed Index data."""
    return {
        "value": 65,
        "value_classification": "Greed",
        "timestamp": str(int(datetime.utcnow().timestamp())),
        "time_until_update": "43200",
    }


@pytest.fixture
def mock_binance_client(monkeypatch, sample_klines, sample_ticker):
    """Mock Binance client functions."""
    mock_get_klines = AsyncMock(return_value=pd.DataFrame(sample_klines))
    mock_batch_get_tickers = AsyncMock(return_value={"BTCUSDT": sample_ticker})
    mock_get_fear_greed = AsyncMock(
        return_value={"value": 65, "classification": "Greed"}
    )

    monkeypatch.setattr("main.get_klines", mock_get_klines)
    monkeypatch.setattr("main.batch_get_tickers", mock_batch_get_tickers)
    monkeypatch.setattr("main.get_fear_greed_index", mock_get_fear_greed)

    return {
        "get_klines": mock_get_klines,
        "batch_get_tickers": mock_batch_get_tickers,
        "get_fear_greed_index": mock_get_fear_greed,
    }


@pytest.fixture
def sample_signal():
    """Sample signal response."""
    return {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "direction": "LONG",
        "confidence": 78.5,
        "ema7": 29300.0,
        "ema25": 28950.0,
        "reason": "EMA 7 crossed above EMA 25 with strong momentum",
        "timestamp": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_chart_data():
    """Sample chart data response."""
    return {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "bars": [
            {
                "time": 1609459200,
                "open": 29000.0,
                "high": 29500.0,
                "low": 28900.0,
                "close": 29300.0,
                "volume": 1234.5,
            }
            for _ in range(50)
        ],
        "ema7": [{"time": 1609459200, "value": 29150.0} for _ in range(50)],
        "ema25": [{"time": 1609459200, "value": 28950.0} for _ in range(50)],
        "rsi": [{"time": 1609459200, "value": 65.5} for _ in range(50)],
        "macd": [{"time": 1609459200, "value": 150.0} for _ in range(50)],
        "signals": [],
        "latest_values": {
            "ema7": 29150.0,
            "ema25": 28950.0,
            "rsi": 65.5,
        },
    }
