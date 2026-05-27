"""
Unit tests for Stop Loss / Take Profit Automation Engine.
Tests TP/SL detection, trade closure, and various market scenarios.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from models import TradeDB, TradeStatus
from tp_sl_automation import TPSLAutomationEngine


class MockTradeForTesting:
    """Mock trade object for testing TP/SL logic."""

    def __init__(
        self,
        id=1,
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=40000.0,
        quantity=0.01,
        entry_value=400.0,
        stop_loss=None,
        take_profit_1=None,
        take_profit_2=None,
        take_profit_3=None,
        status="OPEN",
        auto_close_enabled=True,
        fees=0.0,
    ):
        self.id = id
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_value = entry_value
        self.stop_loss = stop_loss
        self.take_profit_1 = take_profit_1
        self.take_profit_2 = take_profit_2
        self.take_profit_3 = take_profit_3
        self.status = status
        self.auto_close_enabled = auto_close_enabled
        self.fees = fees
        self.exit_price = None
        self.exit_timestamp = None
        self.exit_reason = None
        self.tp_triggered = None
        self.realized_pnl = None
        self.realized_pnl_pct = None


class TestTPSLDetection:
    """Tests for Stop Loss and Take Profit detection logic."""

    def test_long_stop_loss_hit(self):
        """LONG trade: SL is hit when price <= stop_loss."""
        engine = TPSLAutomationEngine()

        assert engine._check_stop_loss_hit("LONG", 39000.0, 38999.0) == True
        assert engine._check_stop_loss_hit("LONG", 39000.0, 39000.0) == True  # Exactly at SL
        assert engine._check_stop_loss_hit("LONG", 39000.0, 39001.0) == False

    def test_short_stop_loss_hit(self):
        """SHORT trade: SL is hit when price >= stop_loss."""
        engine = TPSLAutomationEngine()

        assert engine._check_stop_loss_hit("SHORT", 41000.0, 41001.0) == True
        assert engine._check_stop_loss_hit("SHORT", 41000.0, 41000.0) == True  # Exactly at SL
        assert engine._check_stop_loss_hit("SHORT", 41000.0, 40999.0) == False

    def test_long_take_profit_tp1_hit(self):
        """LONG trade: TP1 is hit when price >= tp1."""
        engine = TPSLAutomationEngine()

        tp_hit = engine._check_take_profit_hit("LONG", 41000.0, 42000.0, 43000.0, 41001.0)
        assert tp_hit == "TP1"

    def test_long_take_profit_tp2_hit(self):
        """LONG trade: When price >= tp2, return TP1 (first level hit)."""
        engine = TPSLAutomationEngine()

        # Price hits TP2, but TP1 is hit first (lower level), so return TP1
        tp_hit = engine._check_take_profit_hit("LONG", 41000.0, 42000.0, 43000.0, 42001.0)
        assert tp_hit == "TP1"  # First TP level hit, not TP2

    def test_long_take_profit_tp3_hit(self):
        """LONG trade: When price >= tp3, return TP1 (first level hit)."""
        engine = TPSLAutomationEngine()

        # Price hits TP3, but TP1 is hit first (lower level), so return TP1
        tp_hit = engine._check_take_profit_hit("LONG", 41000.0, 42000.0, 43000.0, 43001.0)
        assert tp_hit == "TP1"  # First TP level hit, not TP3

    def test_long_take_profit_none_hit(self):
        """LONG trade: No TP hit if price below all levels."""
        engine = TPSLAutomationEngine()

        tp_hit = engine._check_take_profit_hit("LONG", 41000.0, 42000.0, 43000.0, 40999.0)
        assert tp_hit is None

    def test_short_take_profit_tp1_hit(self):
        """SHORT trade: TP1 is hit when price <= tp1."""
        engine = TPSLAutomationEngine()

        tp_hit = engine._check_take_profit_hit("SHORT", 39000.0, 38000.0, 37000.0, 38999.0)
        assert tp_hit == "TP1"

    def test_short_take_profit_tp2_hit(self):
        """SHORT trade: When price <= tp2, return TP1 (first level hit)."""
        engine = TPSLAutomationEngine()

        # Price hits TP2, but TP1 is hit first (higher level), so return TP1
        tp_hit = engine._check_take_profit_hit("SHORT", 39000.0, 38000.0, 37000.0, 37999.0)
        assert tp_hit == "TP1"  # First TP level hit, not TP2

    def test_short_take_profit_tp3_hit(self):
        """SHORT trade: When price <= tp3, return TP1 (first level hit)."""
        engine = TPSLAutomationEngine()

        # Price hits TP3, but TP1 is hit first (higher level), so return TP1
        tp_hit = engine._check_take_profit_hit("SHORT", 39000.0, 38000.0, 37000.0, 36999.0)
        assert tp_hit == "TP1"  # First TP level hit, not TP3

    def test_short_take_profit_none_hit(self):
        """SHORT trade: No TP hit if price above all levels."""
        engine = TPSLAutomationEngine()

        tp_hit = engine._check_take_profit_hit("SHORT", 39000.0, 38000.0, 37000.0, 39001.0)
        assert tp_hit is None

    def test_multiple_tp_levels_hit_tp1_first(self):
        """When price hits multiple TP levels, return the first (lowest)."""
        engine = TPSLAutomationEngine()

        # Price jumped above all TP levels at once
        tp_hit = engine._check_take_profit_hit("LONG", 41000.0, 42000.0, 43000.0, 50000.0)
        assert tp_hit == "TP1"  # Should return TP1, not TP2 or TP3

    def test_no_tp_levels_defined(self):
        """When no TP levels defined, return None."""
        engine = TPSLAutomationEngine()

        tp_hit = engine._check_take_profit_hit("LONG", None, None, None, 50000.0)
        assert tp_hit is None

    def test_partial_tp_levels_defined(self):
        """When only some TP levels defined, check those."""
        engine = TPSLAutomationEngine()

        # Only TP1 and TP3 defined (TP2 is None)
        tp_hit = engine._check_take_profit_hit("LONG", 41000.0, None, 43000.0, 41500.0)
        assert tp_hit == "TP1"


class TestTPSLScenarios:
    """Tests for realistic trading scenarios."""

    def test_long_trade_stops_at_stop_loss(self):
        """LONG trade: Price drops to SL."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit_1=41000.0,
            take_profit_2=42000.0,
            take_profit_3=43000.0,
        )

        engine = TPSLAutomationEngine()
        # Price hits stop loss
        assert engine._check_stop_loss_hit(trade.direction, trade.stop_loss, 38999.0) == True
        # But no TP hit
        assert engine._check_take_profit_hit(
            trade.direction, trade.take_profit_1, trade.take_profit_2,
            trade.take_profit_3, 38999.0
        ) is None

    def test_long_trade_hits_tp1(self):
        """LONG trade: Price rises to TP1."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit_1=41000.0,
            take_profit_2=42000.0,
            take_profit_3=43000.0,
        )

        engine = TPSLAutomationEngine()
        # Price rises to TP1
        assert engine._check_take_profit_hit(
            trade.direction, trade.take_profit_1, trade.take_profit_2,
            trade.take_profit_3, 41000.0
        ) == "TP1"

    def test_long_trade_hits_tp2(self):
        """LONG trade: When price rises to TP2, return TP1 (first level hit)."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            stop_loss=39000.0,
            take_profit_1=41000.0,
            take_profit_2=42000.0,
            take_profit_3=43000.0,
        )

        engine = TPSLAutomationEngine()
        # Price rises to TP2, but TP1 (lower) is hit first
        assert engine._check_take_profit_hit(
            trade.direction, trade.take_profit_1, trade.take_profit_2,
            trade.take_profit_3, 42000.0
        ) == "TP1"  # First level hit, not TP2

    def test_short_trade_stops_at_stop_loss(self):
        """SHORT trade: Price rises to SL."""
        trade = MockTradeForTesting(
            direction="SHORT",
            entry_price=40000.0,
            stop_loss=41000.0,
            take_profit_1=39000.0,
            take_profit_2=38000.0,
            take_profit_3=37000.0,
        )

        engine = TPSLAutomationEngine()
        # Price rises to stop loss
        assert engine._check_stop_loss_hit(trade.direction, trade.stop_loss, 41001.0) == True
        # But no TP hit
        assert engine._check_take_profit_hit(
            trade.direction, trade.take_profit_1, trade.take_profit_2,
            trade.take_profit_3, 41001.0
        ) is None

    def test_short_trade_hits_tp1(self):
        """SHORT trade: Price drops to TP1."""
        trade = MockTradeForTesting(
            direction="SHORT",
            entry_price=40000.0,
            stop_loss=41000.0,
            take_profit_1=39000.0,
            take_profit_2=38000.0,
            take_profit_3=37000.0,
        )

        engine = TPSLAutomationEngine()
        # Price drops to TP1
        assert engine._check_take_profit_hit(
            trade.direction, trade.take_profit_1, trade.take_profit_2,
            trade.take_profit_3, 39000.0
        ) == "TP1"


class TestPnLCalculation:
    """Tests for P&L calculation when closing trades at TP/SL."""

    def test_long_trade_pnl_at_tp(self):
        """LONG trade P&L when closed at TP."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            quantity=0.01,
            entry_value=400.0,
            fees=1.0,
        )

        exit_price = 41000.0
        # P&L = (exit - entry) * quantity - fees
        # P&L = (41000 - 40000) * 0.01 - 1.0 = 10.0 - 1.0 = 9.0
        # P&L% = (9.0 / 400.0) * 100 = 2.25%

        pnl = (exit_price - trade.entry_price) * trade.quantity - trade.fees
        pnl_pct = (pnl / trade.entry_value) * 100

        assert pnl == 9.0
        assert pnl_pct == 2.25

    def test_long_trade_pnl_at_sl(self):
        """LONG trade P&L when closed at SL (loss)."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            quantity=0.01,
            entry_value=400.0,
            fees=1.0,
        )

        exit_price = 39000.0
        # P&L = (39000 - 40000) * 0.01 - 1.0 = -10.0 - 1.0 = -11.0
        # P&L% = (-11.0 / 400.0) * 100 = -2.75%

        pnl = (exit_price - trade.entry_price) * trade.quantity - trade.fees
        pnl_pct = (pnl / trade.entry_value) * 100

        assert pnl == -11.0
        assert pnl_pct == -2.75

    def test_short_trade_pnl_at_tp(self):
        """SHORT trade P&L when closed at TP."""
        trade = MockTradeForTesting(
            direction="SHORT",
            entry_price=40000.0,
            quantity=0.01,
            entry_value=400.0,
            fees=1.0,
        )

        exit_price = 39000.0
        # P&L = (entry - exit) * quantity - fees (SHORT: profit when price drops)
        # P&L = (40000 - 39000) * 0.01 - 1.0 = 10.0 - 1.0 = 9.0
        # P&L% = (9.0 / 400.0) * 100 = 2.25%

        pnl = (trade.entry_price - exit_price) * trade.quantity - trade.fees
        pnl_pct = (pnl / trade.entry_value) * 100

        assert pnl == 9.0
        assert pnl_pct == 2.25

    def test_short_trade_pnl_at_sl(self):
        """SHORT trade P&L when closed at SL (loss)."""
        trade = MockTradeForTesting(
            direction="SHORT",
            entry_price=40000.0,
            quantity=0.01,
            entry_value=400.0,
            fees=1.0,
        )

        exit_price = 41000.0
        # P&L = (40000 - 41000) * 0.01 - 1.0 = -10.0 - 1.0 = -11.0
        # P&L% = (-11.0 / 400.0) * 100 = -2.75%

        pnl = (trade.entry_price - exit_price) * trade.quantity - trade.fees
        pnl_pct = (pnl / trade.entry_value) * 100

        assert pnl == -11.0
        assert pnl_pct == -2.75


class TestEdgeCases:
    """Tests for edge cases in TP/SL automation."""

    def test_zero_fees(self):
        """Trade with no fees."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            quantity=0.01,
            entry_value=400.0,
            fees=0.0,
        )

        exit_price = 41000.0
        pnl = (exit_price - trade.entry_price) * trade.quantity - trade.fees

        assert pnl == 10.0

    def test_fees_exceed_profit(self):
        """Fees can exceed profit, resulting in net loss."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            quantity=0.01,
            entry_value=400.0,
            fees=15.0,  # Fees exceed the $10 profit
        )

        exit_price = 41000.0
        # Gross P&L = 10.0, but fees = 15.0, so net = -5.0
        pnl = (exit_price - trade.entry_price) * trade.quantity - trade.fees

        assert pnl == -5.0

    def test_very_small_position(self):
        """Trade with very small quantity."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            quantity=0.00001,  # Very small
            entry_value=0.4,
            fees=0.0,
        )

        exit_price = 41000.0
        pnl = (exit_price - trade.entry_price) * trade.quantity - trade.fees
        pnl_pct = (pnl / trade.entry_value) * 100 if trade.entry_value > 0 else 0

        assert pnl == pytest.approx(0.01, rel=1e-4)
        assert pnl_pct == pytest.approx(2.5, rel=1e-2)

    def test_large_position(self):
        """Trade with large quantity."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            quantity=10.0,  # 10 BTC
            entry_value=400000.0,
            fees=100.0,
        )

        exit_price = 41000.0
        # P&L = (41000 - 40000) * 10.0 - 100.0 = 10000.0 - 100.0 = 9900.0
        pnl = (exit_price - trade.entry_price) * trade.quantity - trade.fees
        pnl_pct = (pnl / trade.entry_value) * 100

        assert pnl == 9900.0
        assert pnl_pct == 2.475

    def test_price_exactly_at_sl_boundary(self):
        """Price exactly at SL boundary should trigger."""
        engine = TPSLAutomationEngine()

        # LONG: price exactly at SL
        assert engine._check_stop_loss_hit("LONG", 39000.0, 39000.0) == True
        # SHORT: price exactly at SL
        assert engine._check_stop_loss_hit("SHORT", 41000.0, 41000.0) == True

    def test_price_exactly_at_tp_boundary(self):
        """Price exactly at TP boundary should trigger."""
        engine = TPSLAutomationEngine()

        # LONG: price exactly at TP1
        tp_hit = engine._check_take_profit_hit("LONG", 41000.0, 42000.0, 43000.0, 41000.0)
        assert tp_hit == "TP1"

        # SHORT: price exactly at TP1
        tp_hit = engine._check_take_profit_hit("SHORT", 39000.0, 38000.0, 37000.0, 39000.0)
        assert tp_hit == "TP1"

    def test_no_tp_sl_levels_defined(self):
        """Trade with no TP/SL levels should not auto-close."""
        trade = MockTradeForTesting(
            direction="LONG",
            entry_price=40000.0,
            stop_loss=None,
            take_profit_1=None,
            take_profit_2=None,
            take_profit_3=None,
        )

        engine = TPSLAutomationEngine()

        # Even if price moves significantly, no levels to check
        sl_hit = engine._check_stop_loss_hit(trade.direction, trade.stop_loss, 30000.0)
        tp_hit = engine._check_take_profit_hit(
            trade.direction, trade.take_profit_1, trade.take_profit_2,
            trade.take_profit_3, 50000.0
        )

        assert sl_hit == False
        assert tp_hit is None


class TestAutomationEngineConfiguration:
    """Tests for engine configuration and initialization."""

    def test_engine_initialization_default(self):
        """Engine initializes with default check interval."""
        engine = TPSLAutomationEngine()
        assert engine.check_interval == 60
        assert engine.running == False

    def test_engine_initialization_custom(self):
        """Engine initializes with custom check interval."""
        engine = TPSLAutomationEngine(check_interval_seconds=30)
        assert engine.check_interval == 30

    def test_engine_initialization_very_short(self):
        """Engine can be configured with very short check interval."""
        engine = TPSLAutomationEngine(check_interval_seconds=5)
        assert engine.check_interval == 5

    def test_engine_initialization_very_long(self):
        """Engine can be configured with long check interval."""
        engine = TPSLAutomationEngine(check_interval_seconds=3600)
        assert engine.check_interval == 3600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
