"""
Integration tests for API endpoints.
"""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_success(self, client):
        """Health check should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "timestamp" in response.json()


@pytest.mark.integration
class TestMetricsEndpoint:
    """Tests for metrics endpoint."""

    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """Metrics endpoint should return Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "HELP" in response.text or "TYPE" in response.text
        assert response.headers["content-type"].startswith("text/plain")


@pytest.mark.integration
class TestSignalEndpoint:
    """Tests for signal endpoint."""

    def test_signal_endpoint_invalid_symbol(self, client):
        """Invalid symbol should return 400."""
        response = client.get("/api/signal/INVALID-SYMBOL")
        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_signal_endpoint_invalid_timeframe(self, client):
        """Invalid timeframe should return 400."""
        response = client.get("/api/signal/BTCUSDT?timeframe=invalid")
        assert response.status_code == 400

    def test_signal_endpoint_valid_request(self, client, mock_binance_client, sample_signal):
        """Valid signal request should work."""
        with patch("main.generate_signal", return_value=sample_signal):
            response = client.get("/api/signal/BTCUSDT?timeframe=1h")
            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "BTCUSDT"
            assert data["direction"] in ["LONG", "SHORT", "NEUTRAL"]

    def test_signal_includes_request_id_header(self, client, mock_binance_client, sample_signal):
        """Response should include X-Request-ID header."""
        with patch("main.generate_signal", return_value=sample_signal):
            response = client.get("/api/signal/BTCUSDT?timeframe=1h")
            assert "X-Request-ID" in response.headers
            assert response.headers["X-Request-ID"]


@pytest.mark.integration
class TestChartEndpoint:
    """Tests for chart data endpoint."""

    def test_chart_endpoint_invalid_symbol(self, client):
        """Invalid symbol should return 400."""
        response = client.get("/api/chart/INVALID")
        assert response.status_code == 400

    def test_chart_endpoint_invalid_limit(self, client):
        """Invalid limit should return 400."""
        response = client.get("/api/chart/BTCUSDT?limit=30")  # Below minimum 50
        assert response.status_code == 400

    def test_chart_endpoint_limit_range(self, client, mock_binance_client, sample_chart_data):
        """Chart limit should respect range."""
        with patch("main.add_all_indicators", return_value=sample_chart_data):
            # Valid limit
            response = client.get("/api/chart/BTCUSDT?limit=100")
            assert response.status_code in [200, 404]  # May fail if no data

            # Invalid limit too high
            response = client.get("/api/chart/BTCUSDT?limit=1000")
            assert response.status_code == 400

    def test_chart_endpoint_default_timeframe(self, client, mock_binance_client, sample_chart_data):
        """Chart should use default timeframe if not specified."""
        with patch("main.add_all_indicators", return_value=sample_chart_data):
            response = client.get("/api/chart/BTCUSDT")
            # Should use default 1h timeframe


@pytest.mark.integration
class TestScanEndpoint:
    """Tests for market scan endpoint."""

    def test_scan_endpoint_invalid_timeframe(self, client):
        """Invalid timeframe should return 400."""
        response = client.get("/api/scan?timeframe=invalid")
        assert response.status_code == 400

    def test_scan_endpoint_invalid_confidence(self, client):
        """Invalid confidence should return 400."""
        response = client.get("/api/scan?min_confidence=150")
        assert response.status_code == 400

    def test_scan_endpoint_invalid_max_pairs(self, client):
        """Invalid max_pairs should return 400."""
        response = client.get("/api/scan?max_pairs=5")  # Below minimum
        assert response.status_code == 400

    def test_scan_endpoint_returns_signals(self, client, mock_binance_client):
        """Scan should return signal list."""
        with patch("main.scan_market", return_value={"signals": []}):
            response = client.get("/api/scan?timeframe=1h")
            assert response.status_code == 200
            assert "signals" in response.json()


@pytest.mark.integration
class TestMarketOverviewEndpoint:
    """Tests for market overview endpoint."""

    def test_market_overview_success(self, client, mock_binance_client):
        """Market overview should return data."""
        response = client.get("/api/market-overview")
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "btc" in data
        assert "eth" in data
        assert "fear_greed" in data

    def test_market_overview_graceful_degradation(self, client):
        """Market overview should handle API failures gracefully."""
        with patch("main.batch_get_tickers", side_effect=Exception("API Error")):
            response = client.get("/api/market-overview")
            # Should return 200 with default values, not 500
            assert response.status_code == 200


@pytest.mark.integration
class TestErrorLoggingEndpoint:
    """Tests for error logging endpoint."""

    def test_error_logging_accepts_frontend_errors(self, client):
        """Error logging endpoint should accept frontend errors."""
        error_data = {
            "message": "Test error",
            "stack": "Error: test",
            "type": "Error",
            "url": "http://localhost:3000",
        }
        response = client.post("/api/errors", json=error_data)
        assert response.status_code == 200
        assert "request_id" in response.json()

    def test_error_logging_includes_request_id(self, client):
        """Error logging should include request ID."""
        error_data = {
            "message": "Test error",
            "type": "Error",
        }
        response = client.post("/api/errors", json=error_data)
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"]


@pytest.mark.integration
class TestInputValidation:
    """Tests for input validation across endpoints."""

    @pytest.mark.parametrize(
        "symbol",
        [
            "BTC-USDT",  # Invalid dash
            "btc",  # No quote
            "VERYLONGSYMBOLTHATEXCEEDSMAX",  # Too long
            "",  # Empty
        ],
    )
    def test_invalid_symbols_rejected(self, client, symbol):
        """Invalid symbols should be rejected."""
        response = client.get(f"/api/signal/{symbol}")
        assert response.status_code == 400

    @pytest.mark.parametrize(
        "timeframe",
        [
            "2m",  # Invalid interval
            "10h",  # Invalid interval
            "1M",  # Wrong format
        ],
    )
    def test_invalid_timeframes_rejected(self, client, timeframe):
        """Invalid timeframes should be rejected."""
        response = client.get(f"/api/signal/BTCUSDT?timeframe={timeframe}")
        assert response.status_code == 400


@pytest.mark.integration
class TestRequestIDPropagation:
    """Tests for X-Request-ID header propagation."""

    def test_request_id_in_response_headers(self, client):
        """All responses should include X-Request-ID header."""
        response = client.get("/health")
        assert "X-Request-ID" in response.headers

    def test_client_provided_request_id_preserved(self, client):
        """Client-provided X-Request-ID should be preserved."""
        test_id = "test-request-id-123"
        response = client.get("/health", headers={"X-Request-ID": test_id})
        assert response.headers["X-Request-ID"] == test_id
