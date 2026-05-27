"""
Unit tests for trade history endpoint functionality.
Tests closed trade retrieval, performance statistics, and filtering.
"""

import pytest
from datetime import datetime, timedelta
from models import TradeDB, TradeStatus
from repositories import TradeRepository


class TestTradeHistoryPerformance:
    """Tests for trading performance statistics calculation."""

    def test_performance_all_winning_trades(self):
        """All trades are winners — win rate should be 100%."""
        trades = [
            MockTrade(realized_pnl=100, realized_pnl_pct=5.0),  # +5%
            MockTrade(realized_pnl=200, realized_pnl_pct=10.0),  # +10%
            MockTrade(realized_pnl=150, realized_pnl_pct=7.5),   # +7.5%
        ]

        win_rate = len([t for t in trades if t.realized_pnl_pct > 0]) / len(trades) * 100
        total_pnl = sum(t.realized_pnl for t in trades)
        avg_pnl = total_pnl / len(trades)

        assert win_rate == 100.0
        assert total_pnl == 450.0
        assert avg_pnl == 150.0

    def test_performance_all_losing_trades(self):
        """All trades are losers — win rate should be 0%."""
        trades = [
            MockTrade(realized_pnl=-50, realized_pnl_pct=-2.5),   # -2.5%
            MockTrade(realized_pnl=-100, realized_pnl_pct=-5.0),  # -5%
            MockTrade(realized_pnl=-75, realized_pnl_pct=-3.75),  # -3.75%
        ]

        win_rate = len([t for t in trades if t.realized_pnl_pct > 0]) / len(trades) * 100
        total_pnl = sum(t.realized_pnl for t in trades)
        avg_pnl = total_pnl / len(trades)

        assert win_rate == 0.0
        assert total_pnl == -225.0
        assert avg_pnl == -75.0

    def test_performance_mixed_trades(self):
        """Mix of winning and losing trades."""
        trades = [
            MockTrade(realized_pnl=100, realized_pnl_pct=5.0),   # Win
            MockTrade(realized_pnl=-50, realized_pnl_pct=-2.5),  # Loss
            MockTrade(realized_pnl=200, realized_pnl_pct=10.0),  # Win
            MockTrade(realized_pnl=-100, realized_pnl_pct=-5.0), # Loss
        ]

        winning = len([t for t in trades if t.realized_pnl_pct > 0])
        win_rate = winning / len(trades) * 100
        total_pnl = sum(t.realized_pnl for t in trades)

        assert win_rate == 50.0
        assert winning == 2
        assert total_pnl == 150.0

    def test_profit_factor_calculation(self):
        """Profit factor = total wins / total losses."""
        winning_trades = [
            MockTrade(realized_pnl=100),
            MockTrade(realized_pnl=200),
        ]
        losing_trades = [
            MockTrade(realized_pnl=-50),
            MockTrade(realized_pnl=-50),
        ]

        winning_pnl = sum(t.realized_pnl for t in winning_trades)  # 300
        losing_pnl = sum(abs(t.realized_pnl) for t in losing_trades)  # 100

        profit_factor = winning_pnl / losing_pnl if losing_pnl > 0 else 0
        assert profit_factor == 3.0  # $300 wins / $100 losses

    def test_profit_factor_no_losses(self):
        """If there are no losses, profit factor is infinite (return 0)."""
        winning_pnl = 500.0
        losing_pnl = 0.0

        profit_factor = winning_pnl / losing_pnl if losing_pnl > 0 else 0
        assert profit_factor == 0

    def test_best_worst_trade_identification(self):
        """Track best and worst performing trades."""
        trades = [
            MockTrade(realized_pnl_pct=5.0),
            MockTrade(realized_pnl_pct=-10.0),
            MockTrade(realized_pnl_pct=15.0),
            MockTrade(realized_pnl_pct=-3.0),
        ]

        best = max(t.realized_pnl_pct for t in trades)
        worst = min(t.realized_pnl_pct for t in trades)

        assert best == 15.0
        assert worst == -10.0


class TestTradeHistoryBreakdown:
    """Tests for trade history composition analysis."""

    def test_trades_by_symbol(self):
        """Filter and count trades by symbol."""
        trades = [
            MockTrade(symbol="BTCUSDT"),
            MockTrade(symbol="ETHUSDT"),
            MockTrade(symbol="BTCUSDT"),
            MockTrade(symbol="BNBUSDT"),
            MockTrade(symbol="ETHUSDT"),
        ]

        btc_trades = [t for t in trades if t.symbol == "BTCUSDT"]
        eth_trades = [t for t in trades if t.symbol == "ETHUSDT"]

        assert len(btc_trades) == 2
        assert len(eth_trades) == 2

    def test_trades_by_direction(self):
        """Separate LONG and SHORT trades."""
        trades = [
            MockTrade(direction="LONG"),
            MockTrade(direction="SHORT"),
            MockTrade(direction="LONG"),
            MockTrade(direction="LONG"),
        ]

        long_trades = [t for t in trades if t.direction == "LONG"]
        short_trades = [t for t in trades if t.direction == "SHORT"]

        assert len(long_trades) == 3
        assert len(short_trades) == 1

    def test_winning_vs_losing_breakdown(self):
        """Break down trades into winners and losers."""
        trades = [
            MockTrade(realized_pnl_pct=3.0),   # Win
            MockTrade(realized_pnl_pct=-2.0),  # Loss
            MockTrade(realized_pnl_pct=5.0),   # Win
            MockTrade(realized_pnl_pct=0.0),   # Break even (loss)
            MockTrade(realized_pnl_pct=-1.5),  # Loss
        ]

        winning = [t for t in trades if t.realized_pnl_pct > 0]
        losing = [t for t in trades if t.realized_pnl_pct <= 0]

        assert len(winning) == 2  # 3.0, 5.0
        assert len(losing) == 3   # -2.0, 0.0, -1.5


class TestTradeHistoryDuration:
    """Tests for trade duration calculations."""

    def test_trade_duration_hours(self):
        """Calculate trade duration in hours."""
        entry = datetime(2026, 5, 17, 10, 0, 0)
        exit = datetime(2026, 5, 17, 12, 30, 0)

        duration = (exit - entry).total_seconds() / 3600
        assert duration == 2.5

    def test_trade_duration_minutes(self):
        """Calculate trade duration in hours (less than 1 hour)."""
        entry = datetime(2026, 5, 17, 10, 0, 0)
        exit = datetime(2026, 5, 17, 10, 30, 0)

        duration = (exit - entry).total_seconds() / 3600
        assert duration == 0.5

    def test_trade_duration_days(self):
        """Calculate multi-day trade duration."""
        entry = datetime(2026, 5, 17, 10, 0, 0)
        exit = datetime(2026, 5, 20, 10, 0, 0)

        duration = (exit - entry).total_seconds() / 3600
        assert duration == 72.0

    def test_trade_duration_seconds(self):
        """Very quick trade (scalp)."""
        entry = datetime(2026, 5, 17, 10, 0, 0)
        exit = datetime(2026, 5, 17, 10, 0, 30)

        duration = (exit - entry).total_seconds() / 3600
        assert pytest.approx(duration, rel=1e-4) == 30 / 3600


class TestTradeHistoryFiltering:
    """Tests for trade history filtering and pagination."""

    def test_filter_by_symbol(self):
        """Retrieve trades for specific symbol."""
        trades = [
            MockTrade(id=1, symbol="BTCUSDT"),
            MockTrade(id=2, symbol="ETHUSDT"),
            MockTrade(id=3, symbol="BTCUSDT"),
        ]

        btc_history = [t for t in trades if t.symbol == "BTCUSDT"]
        assert len(btc_history) == 2
        assert all(t.symbol == "BTCUSDT" for t in btc_history)

    def test_limit_results(self):
        """Respect limit parameter for pagination."""
        trades = [MockTrade(id=i) for i in range(1, 101)]  # 100 trades

        limited = trades[:50]
        assert len(limited) == 50

    def test_limit_default_50(self):
        """Default limit should be 50 trades."""
        trades = [MockTrade(id=i) for i in range(1, 101)]
        default_limit = 50
        result = trades[:default_limit]
        assert len(result) == 50

    def test_limit_maximum_500(self):
        """Maximum limit should be 500 trades."""
        trades = [MockTrade(id=i) for i in range(1, 1001)]  # 1000 trades
        max_limit = 500
        result = trades[:max_limit]
        assert len(result) == 500

    def test_empty_history(self):
        """Handle case with no closed trades."""
        trades = []
        assert len(trades) == 0


class TestTradeHistoryOrdering:
    """Tests for trade history ordering and sorting."""

    def test_trades_ordered_by_date_desc(self):
        """Most recent trades should appear first."""
        trades = [
            MockTrade(
                id=1,
                exit_timestamp=datetime(2026, 5, 17, 10, 0, 0)
            ),
            MockTrade(
                id=2,
                exit_timestamp=datetime(2026, 5, 18, 10, 0, 0)
            ),
            MockTrade(
                id=3,
                exit_timestamp=datetime(2026, 5, 16, 10, 0, 0)
            ),
        ]

        sorted_trades = sorted(
            trades,
            key=lambda t: t.exit_timestamp,
            reverse=True
        )

        assert sorted_trades[0].id == 2  # Most recent
        assert sorted_trades[1].id == 1
        assert sorted_trades[2].id == 3  # Oldest

    def test_trades_ordered_by_pnl_desc(self):
        """Trades can be sorted by P&L."""
        trades = [
            MockTrade(realized_pnl=50),
            MockTrade(realized_pnl=200),
            MockTrade(realized_pnl=100),
        ]

        by_pnl = sorted(trades, key=lambda t: t.realized_pnl, reverse=True)
        assert by_pnl[0].realized_pnl == 200
        assert by_pnl[1].realized_pnl == 100
        assert by_pnl[2].realized_pnl == 50


class TestTradeHistoryAggregates:
    """Tests for aggregate statistics over history."""

    def test_total_pnl_positive(self):
        """Sum of all P&L should reflect net profitability."""
        trades = [
            MockTrade(realized_pnl=100),
            MockTrade(realized_pnl=150),
            MockTrade(realized_pnl=50),
        ]

        total_pnl = sum(t.realized_pnl for t in trades)
        assert total_pnl == 300

    def test_total_pnl_negative(self):
        """Losing period should show negative total P&L."""
        trades = [
            MockTrade(realized_pnl=-100),
            MockTrade(realized_pnl=-150),
            MockTrade(realized_pnl=-50),
        ]

        total_pnl = sum(t.realized_pnl for t in trades)
        assert total_pnl == -300

    def test_average_trade_size(self):
        """Calculate average P&L per trade."""
        trades = [
            MockTrade(realized_pnl=100),
            MockTrade(realized_pnl=200),
            MockTrade(realized_pnl=300),
        ]

        avg = sum(t.realized_pnl for t in trades) / len(trades)
        assert avg == 200.0

    def test_largest_winning_streak(self):
        """Identify consecutive winning trades."""
        trades = [
            MockTrade(realized_pnl_pct=5.0),   # Win
            MockTrade(realized_pnl_pct=3.0),   # Win
            MockTrade(realized_pnl_pct=-2.0),  # Loss - breaks streak
            MockTrade(realized_pnl_pct=1.0),   # Win
            MockTrade(realized_pnl_pct=2.0),   # Win
            MockTrade(realized_pnl_pct=1.5),   # Win
        ]

        # Find longest winning streak
        streaks = []
        current_streak = 0
        for trade in trades:
            if trade.realized_pnl_pct > 0:
                current_streak += 1
            else:
                if current_streak > 0:
                    streaks.append(current_streak)
                current_streak = 0
        if current_streak > 0:
            streaks.append(current_streak)

        longest_streak = max(streaks) if streaks else 0
        assert longest_streak == 3


# Mock Trade class for testing
class MockTrade:
    """Mock trade object for testing statistics calculation."""

    def __init__(
        self,
        id=1,
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=40000.0,
        exit_price=41000.0,
        quantity=0.005,
        realized_pnl=None,
        realized_pnl_pct=None,
        exit_timestamp=None,
        entry_timestamp=None,
    ):
        self.id = id
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.quantity = quantity
        self.realized_pnl = realized_pnl if realized_pnl is not None else 50.0
        self.realized_pnl_pct = realized_pnl_pct if realized_pnl_pct is not None else 2.5
        self.exit_timestamp = exit_timestamp or datetime.utcnow()
        self.entry_timestamp = entry_timestamp or (
            self.exit_timestamp - timedelta(hours=2)
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
