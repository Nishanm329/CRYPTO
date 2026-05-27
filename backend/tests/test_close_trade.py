"""
Unit tests for close trade endpoint functionality.
Tests trade closure, P&L calculation, and state transitions.
"""

import pytest
from datetime import datetime, timedelta
from models import TradeDB, TradeStatus
from trade_validator import PaperTradingSimulator


class TestCloseTrade:
    """Tests for trade closing logic."""

    def test_close_trade_long_profit(self):
        """Close a LONG trade with profit."""
        # Entry: $40,000 @ 0.005 BTC = $200
        # Exit: $41,000 @ 0.005 BTC = $205
        # P&L: +$5 (+2.5%)

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=41000.0,
            quantity=0.005,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 5.0
        assert pnl["net_pnl"] == 5.0
        assert pnl["pnl_pct"] == 2.5

    def test_close_trade_long_loss(self):
        """Close a LONG trade with loss."""
        # Entry: $40,000 @ 0.005 BTC = $200
        # Exit: $39,000 @ 0.005 BTC = $195
        # P&L: -$5 (-2.5%)

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=39000.0,
            quantity=0.005,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == -5.0
        assert pnl["net_pnl"] == -5.0
        assert pnl["pnl_pct"] == -2.5

    def test_close_trade_short_profit(self):
        """Close a SHORT trade with profit."""
        # Entry: $40,000 (SELL 0.005 BTC)
        # Exit: $39,000 (BUY back 0.005 BTC)
        # P&L: +$5 (+2.5%)

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=39000.0,
            quantity=0.005,
            direction="SHORT",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 5.0
        assert pnl["net_pnl"] == 5.0
        assert pnl["pnl_pct"] == 2.5

    def test_close_trade_short_loss(self):
        """Close a SHORT trade with loss."""
        # Entry: $40,000 (SELL 0.005 BTC)
        # Exit: $41,000 (BUY back 0.005 BTC)
        # P&L: -$5 (-2.5%)

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=41000.0,
            quantity=0.005,
            direction="SHORT",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == -5.0
        assert pnl["net_pnl"] == -5.0
        assert pnl["pnl_pct"] == -2.5

    def test_close_trade_with_fees(self):
        """Close trade with transaction fees."""
        # P&L before fees: $5
        # Fees: $1 (0.1% on $500 exit value)
        # P&L after fees: $4

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=41000.0,
            quantity=0.005,
            direction="LONG",
            fees=1.0,
        )

        assert pnl["gross_pnl"] == 5.0
        assert pnl["net_pnl"] == 4.0
        assert pnl["pnl_pct"] == 2.0

    def test_close_trade_break_even(self):
        """Close trade at break even price."""
        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=40000.0,
            quantity=0.005,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 0.0
        assert pnl["net_pnl"] == 0.0
        assert pnl["pnl_pct"] == 0.0

    def test_close_trade_duration_calculation(self):
        """Calculate trade duration correctly."""
        entry_time = datetime(2026, 5, 17, 10, 0, 0)
        exit_time = datetime(2026, 5, 17, 12, 30, 0)

        duration = (exit_time - entry_time).total_seconds() / 3600
        assert duration == 2.5  # 2.5 hours

    def test_close_trade_large_quantities(self):
        """Close trade with large quantity."""
        # 10 ETH @ $2000 entry
        # Exit @ $2100
        # P&L: (2100 - 2000) * 10 = $1000

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=2000.0,
            exit_price=2100.0,
            quantity=10.0,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 1000.0
        assert pnl["pnl_pct"] == 5.0

    def test_close_trade_small_quantities(self):
        """Close trade with small quantity."""
        # 0.00001 BTC @ $40000
        # Exit @ $41000
        # P&L: (41000 - 40000) * 0.00001 = $0.01

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=41000.0,
            quantity=0.00001,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 0.01
        assert pnl["pnl_pct"] == 2.5

    def test_close_trade_high_volatility(self):
        """Close trade with high price movement (stop loss scenario)."""
        # Entry: $40000
        # Exit: $30000 (25% loss)
        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=30000.0,
            quantity=1.0,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == -10000.0
        assert pnl["pnl_pct"] == -25.0

    def test_close_trade_take_profit_scenario(self):
        """Close trade at take profit level (large win)."""
        # Entry: $40000
        # Exit: $50000 (25% gain)
        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=50000.0,
            quantity=1.0,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 10000.0
        assert pnl["pnl_pct"] == 25.0


class TestCloseTradeEdgeCases:
    """Edge case tests for trade closing."""

    def test_close_trade_zero_quantity(self):
        """Closing a trade with zero quantity should be handled."""
        # This shouldn't happen in practice due to validation,
        # but the P&L calculation should handle it
        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=41000.0,
            quantity=0.0,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 0.0
        assert pnl["pnl_pct"] == 0.0

    def test_close_trade_identical_entry_exit(self):
        """Close trade at exact entry price (break even)."""
        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=100.0,
            exit_price=100.0,
            quantity=1.0,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 0.0
        assert pnl["net_pnl"] == 0.0
        assert pnl["pnl_pct"] == 0.0

    def test_close_trade_extreme_price_movement(self):
        """Handle extreme price movements."""
        # Price drops to 1 (from 40000)
        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=1.0,
            quantity=1.0,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == -39999.0
        assert pnl["pnl_pct"] == pytest.approx(-99.9975, rel=1e-4)

    def test_close_trade_fees_exceed_profit(self):
        """Fees can exceed profit, resulting in net loss."""
        # Gross profit: $5
        # Fees: $10
        # Net result: -$5 loss
        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=41000.0,
            quantity=0.005,
            direction="LONG",
            fees=10.0,
        )

        assert pnl["gross_pnl"] == 5.0
        assert pnl["net_pnl"] == -5.0
        assert pnl["pnl_pct"] == -2.5


class TestCloseTradeMultipleScenarios:
    """Test realistic trading scenarios."""

    def test_scalp_trade_quick_exit(self):
        """Scalp trade: quick entry and exit."""
        # Entry: $2000 (1 ETH)
        # Exit: $2010 (30 minutes later)
        # P&L: +$10 (+0.5%)

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=2000.0,
            exit_price=2010.0,
            quantity=1.0,
            direction="LONG",
            fees=2.0,
        )

        assert pnl["gross_pnl"] == 10.0
        assert pnl["net_pnl"] == 8.0
        assert pnl["pnl_pct"] == 0.4

    def test_swing_trade_medium_hold(self):
        """Swing trade: held for several hours."""
        # Entry: $2000
        # Exit: $2200 (12 hours later)
        # P&L: +$200 (+10%)

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=2000.0,
            exit_price=2200.0,
            quantity=1.0,
            direction="LONG",
            fees=2.0,
        )

        assert pnl["gross_pnl"] == 200.0
        assert pnl["net_pnl"] == 198.0
        assert pnl["pnl_pct"] == 9.9

    def test_position_trade_long_hold(self):
        """Position trade: held for days."""
        # Entry: $40000
        # Exit: $48000 (price up 20%)
        # P&L: +$8000 (+20%)

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=40000.0,
            exit_price=48000.0,
            quantity=1.0,
            direction="LONG",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 8000.0
        assert pnl["net_pnl"] == 8000.0
        assert pnl["pnl_pct"] == 20.0

    def test_short_trade_profit(self):
        """Short trade that's profitable."""
        # Short entry: $50000 (sell high)
        # Short exit: $45000 (buy back low)
        # P&L: +$5000 (+10%)

        pnl = PaperTradingSimulator.calculate_pnl(
            entry_price=50000.0,
            exit_price=45000.0,
            quantity=1.0,
            direction="SHORT",
            fees=0.0,
        )

        assert pnl["gross_pnl"] == 5000.0
        assert pnl["pnl_pct"] == 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
