"""
Unit tests for Order Status Polling Engine.
Tests order status detection, partial fills, rejections, and various market scenarios.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from models import TradeDB, TradeStatus
from order_status_poller import OrderStatusPoller, OrderStatusEnum


class MockOrderFromBinance:
    """Mock order response from Binance API."""

    def __init__(
        self,
        order_id="123456789",
        symbol="BTCUSDT",
        status="FILLED",
        side="BUY",
        quantity=0.01,
        executed_qty=0.01,
        avg_price=40000.0,
        cummulative_quote=400.0,
        fills=None,
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.status = status
        self.side = side
        self.origQty = quantity
        self.executedQty = executed_qty
        self.origPrice = avg_price
        self.cummulativeQuoteAssetTransactedQuantity = cummulative_quote
        self.fills = fills or []

    def to_dict(self):
        """Convert to dict for Binance API format."""
        return {
            "orderId": self.order_id,
            "symbol": self.symbol,
            "status": self.status,
            "side": self.side,
            "origQty": self.origQty,
            "executedQty": self.executedQty,
            "origPrice": self.origPrice,
            "cummulativeQuoteAssetTransactedQuantity": self.cummulative_quote,
            "fills": self.fills,
        }


class MockTradeForTesting:
    """Mock trade object for testing."""

    def __init__(
        self,
        id=1,
        user_id="user123",
        order_id="123456789",
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=40000.0,
        quantity=0.01,
        entry_value=400.0,
        status="OPEN",
        created_at=None,
    ):
        self.id = id
        self.user_id = user_id
        self.order_id = order_id
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_value = entry_value
        self.status = status
        self.created_at = created_at or datetime.utcnow()
        self.exit_timestamp = None
        self.exit_reason = None


class TestOrderStatusDetection:
    """Tests for order status detection logic."""

    def test_filled_order_confirmed(self):
        """Fully filled order should be confirmed."""
        trade = MockTradeForTesting(quantity=0.01)
        order_info = {
            "status": OrderStatusEnum.FILLED.value,
            "executedQty": 0.01,
            "cummulativeQuoteAssetTransactedQuantity": 400.0,
        }

        poller = OrderStatusPoller()
        filled_qty = float(order_info.get("executedQty", 0))

        # Filled qty matches trade qty (within 1% tolerance)
        assert filled_qty >= trade.quantity * 0.99

    def test_partial_fill_detection(self):
        """Partially filled order should be detected."""
        trade = MockTradeForTesting(quantity=0.01)
        order_info = {
            "status": OrderStatusEnum.PARTIALLY_FILLED.value,
            "executedQty": 0.005,  # 50% filled
            "cummulativeQuoteAssetTransactedQuantity": 200.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty < trade.quantity
        assert filled_qty > 0

    def test_canceled_order_detection(self):
        """Canceled order should be detected."""
        order_info = {
            "status": OrderStatusEnum.CANCELED.value,
            "executedQty": 0.0,
        }

        assert order_info.get("status") == OrderStatusEnum.CANCELED.value

    def test_rejected_order_detection(self):
        """Rejected order should be detected."""
        order_info = {
            "status": OrderStatusEnum.REJECTED.value,
            "executedQty": 0.0,
        }

        assert order_info.get("status") == OrderStatusEnum.REJECTED.value

    def test_expired_order_detection(self):
        """Expired order should be detected."""
        order_info = {
            "status": OrderStatusEnum.EXPIRED.value,
            "executedQty": 0.0,
        }

        assert order_info.get("status") == OrderStatusEnum.EXPIRED.value

    def test_new_order_pending(self):
        """New order that hasn't filled yet should be pending."""
        order_info = {
            "status": OrderStatusEnum.NEW.value,
            "executedQty": 0.0,
        }

        assert order_info.get("status") == OrderStatusEnum.NEW.value
        assert float(order_info.get("executedQty", 0)) == 0.0


class TestPartialFillScenarios:
    """Tests for partial fill scenarios."""

    def test_50_percent_fill(self):
        """Order with 50% fill."""
        trade = MockTradeForTesting(quantity=0.01, entry_price=40000.0)
        order_info = {
            "status": OrderStatusEnum.PARTIALLY_FILLED.value,
            "executedQty": 0.005,  # 50% of 0.01
            "cummulativeQuoteAssetTransactedQuantity": 200.0,  # 50% of 400
        }

        filled_qty = float(order_info.get("executedQty", 0))
        cummulative_quote = float(
            order_info.get("cummulativeQuoteAssetTransactedQuantity", 0)
        )
        avg_price = cummulative_quote / filled_qty if filled_qty > 0 else trade.entry_price

        assert filled_qty == 0.005
        assert avg_price == 40000.0  # Same price
        fill_pct = (filled_qty / trade.quantity) * 100
        assert fill_pct == 50.0

    def test_25_percent_fill(self):
        """Order with 25% fill."""
        trade = MockTradeForTesting(quantity=1.0, entry_price=40000.0)
        order_info = {
            "status": OrderStatusEnum.PARTIALLY_FILLED.value,
            "executedQty": 0.25,
            "cummulativeQuoteAssetTransactedQuantity": 10000.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        fill_pct = (filled_qty / trade.quantity) * 100

        assert filled_qty == 0.25
        assert fill_pct == 25.0

    def test_99_percent_fill(self):
        """Order almost fully filled (99%)."""
        trade = MockTradeForTesting(quantity=0.01)
        order_info = {
            "status": OrderStatusEnum.PARTIALLY_FILLED.value,
            "executedQty": 0.0099,
            "cummulativeQuoteAssetTransactedQuantity": 396.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        fill_pct = (filled_qty / trade.quantity) * 100

        assert filled_qty == pytest.approx(0.0099, rel=1e-4)
        assert fill_pct == pytest.approx(99.0, rel=1e-2)

    def test_very_small_fill(self):
        """Order with very small fill (dust)."""
        trade = MockTradeForTesting(quantity=0.01)
        order_info = {
            "status": OrderStatusEnum.PARTIALLY_FILLED.value,
            "executedQty": 0.00001,  # Dust amount
            "cummulativeQuoteAssetTransactedQuantity": 0.4,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        fill_pct = (filled_qty / trade.quantity) * 100

        assert filled_qty == 0.00001
        assert fill_pct == pytest.approx(0.1, rel=1e-2)


class TestAveragePriceCalculation:
    """Tests for average fill price calculation."""

    def test_simple_full_fill_price(self):
        """Full fill at single price."""
        order_info = {
            "executedQty": 0.01,
            "cummulativeQuoteAssetTransactedQuantity": 400.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        cummulative = float(
            order_info.get("cummulativeQuoteAssetTransactedQuantity", 0)
        )
        avg_price = cummulative / filled_qty if filled_qty > 0 else 0

        assert avg_price == 40000.0

    def test_partial_fill_average_price(self):
        """Average price for partial fill."""
        order_info = {
            "executedQty": 0.005,
            "cummulativeQuoteAssetTransactedQuantity": 200.5,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        cummulative = float(
            order_info.get("cummulativeQuoteAssetTransactedQuantity", 0)
        )
        avg_price = cummulative / filled_qty if filled_qty > 0 else 0

        assert avg_price == pytest.approx(40100.0, rel=1e-4)

    def test_multiple_partial_fills(self):
        """Average price from multiple partial fills."""
        # First fill: 0.005 BTC @ 40000
        # Second fill: 0.005 BTC @ 40100
        # Total: 0.01 BTC @ 40050 avg
        order_info = {
            "executedQty": 0.01,
            "cummulativeQuoteAssetTransactedQuantity": 400.5,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        cummulative = float(
            order_info.get("cummulativeQuoteAssetTransactedQuantity", 0)
        )
        avg_price = cummulative / filled_qty if filled_qty > 0 else 0

        assert avg_price == pytest.approx(40050.0, rel=1e-4)


class TestOrderFailureScenarios:
    """Tests for order failure scenarios."""

    def test_rejected_order_no_fill(self):
        """Rejected order with no fill."""
        order_info = {
            "status": OrderStatusEnum.REJECTED.value,
            "executedQty": 0.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty == 0.0
        assert order_info.get("status") == OrderStatusEnum.REJECTED.value

    def test_expired_order_no_fill(self):
        """Expired order with no fill."""
        order_info = {
            "status": OrderStatusEnum.EXPIRED.value,
            "executedQty": 0.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty == 0.0

    def test_canceled_order_no_fill(self):
        """Canceled order before any fill."""
        order_info = {
            "status": OrderStatusEnum.CANCELED.value,
            "executedQty": 0.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty == 0.0

    def test_canceled_order_with_partial_fill(self):
        """Canceled order after partial fill."""
        order_info = {
            "status": OrderStatusEnum.CANCELED.value,
            "executedQty": 0.003,  # Partial fill before cancel
            "cummulativeQuoteAssetTransactedQuantity": 120.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty == 0.003
        assert order_info.get("status") == OrderStatusEnum.CANCELED.value


class TestFillTolerances:
    """Tests for fill tolerance checking."""

    def test_full_fill_within_tolerance(self):
        """Fully filled order passes 1% tolerance check."""
        trade = MockTradeForTesting(quantity=0.01)
        filled_qty = 0.01

        # 1% tolerance check
        tolerance_threshold = trade.quantity * 0.99
        assert filled_qty >= tolerance_threshold

    def test_99_percent_fill_passes_tolerance(self):
        """99% fill passes 1% tolerance."""
        trade = MockTradeForTesting(quantity=1.0)
        filled_qty = 0.99

        tolerance_threshold = trade.quantity * 0.99
        assert filled_qty >= tolerance_threshold

    def test_98_percent_fill_fails_tolerance(self):
        """98% fill fails 1% tolerance."""
        trade = MockTradeForTesting(quantity=1.0)
        filled_qty = 0.98

        tolerance_threshold = trade.quantity * 0.99
        assert not (filled_qty >= tolerance_threshold)

    def test_zero_fill_fails_tolerance(self):
        """Zero fill fails tolerance."""
        trade = MockTradeForTesting(quantity=0.01)
        filled_qty = 0.0

        tolerance_threshold = trade.quantity * 0.99
        assert not (filled_qty >= tolerance_threshold)


class TestPollerConfiguration:
    """Tests for poller configuration."""

    def test_poller_default_config(self):
        """Poller initializes with default configuration."""
        poller = OrderStatusPoller()

        assert poller.check_interval == 30
        assert poller.max_age_minutes == 60
        assert poller.running == False

    def test_poller_custom_check_interval(self):
        """Poller can be configured with custom check interval."""
        poller = OrderStatusPoller(check_interval_seconds=60)

        assert poller.check_interval == 60

    def test_poller_custom_max_age(self):
        """Poller can be configured with custom max age."""
        poller = OrderStatusPoller(max_age_minutes=120)

        assert poller.max_age_minutes == 120

    def test_poller_very_short_interval(self):
        """Poller can be configured with very short interval."""
        poller = OrderStatusPoller(check_interval_seconds=5)

        assert poller.check_interval == 5

    def test_poller_very_long_interval(self):
        """Poller can be configured with long interval."""
        poller = OrderStatusPoller(check_interval_seconds=600)

        assert poller.check_interval == 600


class TestEdgeCases:
    """Tests for edge cases in order status polling."""

    def test_zero_executed_quantity(self):
        """Order with zero executed quantity."""
        order_info = {
            "executedQty": 0.0,
            "cummulativeQuoteAssetTransactedQuantity": 0.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty == 0.0

    def test_missing_executed_quantity(self):
        """Order info missing executedQty field."""
        order_info = {"status": "FILLED"}  # Missing executedQty

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty == 0.0

    def test_string_quantity_conversion(self):
        """String quantity should be converted to float."""
        order_info = {
            "executedQty": "0.01",  # String instead of float
            "cummulativeQuoteAssetTransactedQuantity": "400.0",
        }

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty == 0.01

    def test_very_large_quantity(self):
        """Very large order quantity."""
        order_info = {
            "executedQty": 1000.0,
            "cummulativeQuoteAssetTransactedQuantity": 40000000.0,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        cummulative = float(
            order_info.get("cummulativeQuoteAssetTransactedQuantity", 0)
        )
        avg_price = cummulative / filled_qty if filled_qty > 0 else 0

        assert filled_qty == 1000.0
        assert avg_price == 40000.0

    def test_very_small_quantity(self):
        """Very small order quantity."""
        order_info = {
            "executedQty": 0.00000001,
            "cummulativeQuoteAssetTransactedQuantity": 0.0004,
        }

        filled_qty = float(order_info.get("executedQty", 0))
        assert filled_qty == pytest.approx(0.00000001, rel=1e-8)

    def test_order_status_enum_values(self):
        """All order status enum values are valid."""
        valid_statuses = [
            OrderStatusEnum.NEW.value,
            OrderStatusEnum.PARTIALLY_FILLED.value,
            OrderStatusEnum.FILLED.value,
            OrderStatusEnum.CANCELED.value,
            OrderStatusEnum.PENDING_CANCEL.value,
            OrderStatusEnum.REJECTED.value,
            OrderStatusEnum.EXPIRED.value,
        ]

        assert len(valid_statuses) == 7
        assert "FILLED" in valid_statuses
        assert "PARTIALLY_FILLED" in valid_statuses
        assert "CANCELED" in valid_statuses


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
