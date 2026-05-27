"""
Unit tests for performance analytics.

Tests cover:
- Win rate and profit calculations
- Sharpe ratio, Sortino ratio, Calmar ratio
- Maximum drawdown and recovery factor
- Trade duration metrics
- Statistical performance analysis
- Report generation
"""

import pytest
import asyncio
import math
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from performance_analytics import (
    TradeAnalyzer,
    PortfolioAnalyzer,
    DrawdownAnalyzer,
    StatisticalAnalyzer,
    PerformanceReportGenerator,
    MetricType,
)
from models import TradeDB, TradeStatus
from db import SessionLocal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def db():
    """Create in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    from models import Base

    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def winning_trade():
    """Create a profitable closed trade."""
    return TradeDB(
        id=1,
        user_id="test_user",
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=40000.0,
        exit_price=41234.56,
        quantity=0.1,
        exit_quantity=0.1,
        entry_value=4000.0,
        order_id="order1",
        status=TradeStatus.CLOSED.value,
        entry_timestamp=datetime.utcnow() - timedelta(days=1),
        exit_timestamp=datetime.utcnow(),
        realized_pnl=123.456,
        realized_pnl_pct=3.09,
        auto_close_enabled=True,
        stop_loss=39000.0,
        take_profit_1=42000.0,
        fees=10.0,
    )


@pytest.fixture
def losing_trade():
    """Create a losing closed trade."""
    return TradeDB(
        id=2,
        user_id="test_user",
        symbol="ETHUSDT",
        direction="SHORT",
        entry_price=2500.0,
        exit_price=2550.0,
        quantity=1.0,
        exit_quantity=1.0,
        entry_value=2500.0,
        order_id="order2",
        status=TradeStatus.CLOSED.value,
        entry_timestamp=datetime.utcnow() - timedelta(hours=12),
        exit_timestamp=datetime.utcnow(),
        realized_pnl=-50.0,
        realized_pnl_pct=-2.0,
        auto_close_enabled=True,
        stop_loss=2600.0,
        take_profit_1=2400.0,
        fees=5.0,
    )


@pytest.fixture
def breakeven_trade():
    """Create a trade with near-zero P&L."""
    return TradeDB(
        id=3,
        user_id="test_user",
        symbol="BNBUSDT",
        direction="LONG",
        entry_price=500.0,
        exit_price=500.05,
        quantity=1.0,
        exit_quantity=1.0,
        entry_value=500.0,
        order_id="order3",
        status=TradeStatus.CLOSED.value,
        entry_timestamp=datetime.utcnow() - timedelta(hours=2),
        exit_timestamp=datetime.utcnow(),
        realized_pnl=0.0005,
        realized_pnl_pct=0.0001,
        auto_close_enabled=True,
        stop_loss=490.0,
        take_profit_1=510.0,
        fees=0.5,
    )


# ============================================================================
# Tests: TradeAnalyzer
# ============================================================================


class TestTradeAnalyzer:
    """Test individual trade analysis."""

    def test_trade_metrics_profitable(self, winning_trade):
        """Test metrics for profitable trade."""
        metrics = TradeAnalyzer.calculate_trade_metrics(winning_trade)

        assert metrics["trade_id"] == 1
        assert metrics["realized_pnl"] == 123.456
        assert metrics["realized_pnl_pct"] == 3.09
        assert metrics["is_profitable"] is True
        assert metrics["duration_hours"] == pytest.approx(24, rel=0.1)
        assert metrics["fees"] == 10.0

    def test_trade_metrics_losing(self, losing_trade):
        """Test metrics for losing trade."""
        metrics = TradeAnalyzer.calculate_trade_metrics(losing_trade)

        assert metrics["is_profitable"] is False
        assert metrics["realized_pnl"] == -50.0
        assert metrics["realized_pnl_pct"] == -2.0

    def test_trade_metrics_short(self, losing_trade):
        """Test metrics for SHORT trade."""
        metrics = TradeAnalyzer.calculate_trade_metrics(losing_trade)

        assert metrics["direction"] == "SHORT"

    def test_trade_metrics_rr_ratio(self, winning_trade):
        """Test risk/reward ratio calculation."""
        metrics = TradeAnalyzer.calculate_trade_metrics(winning_trade)

        # RR = (TP - entry) / (entry - SL)
        # (42000 - 40000) / (40000 - 39000) = 2000 / 1000 = 2.0
        assert metrics["rr_ratio"] == pytest.approx(2.0, rel=1e-4)

    def test_is_profitable_true(self, winning_trade):
        """Test profitability check for winner."""
        assert TradeAnalyzer.is_profitable(winning_trade) is True

    def test_is_profitable_false(self, losing_trade):
        """Test profitability check for loser."""
        assert TradeAnalyzer.is_profitable(losing_trade) is False


# ============================================================================
# Tests: PortfolioAnalyzer
# ============================================================================


class TestPortfolioAnalyzer:
    """Test portfolio-level analysis."""

    def test_win_metrics_mixed(self, winning_trade, losing_trade):
        """Test win/loss metrics with mixed trades."""
        trades = [winning_trade, losing_trade]
        metrics = PortfolioAnalyzer.calculate_win_metrics(trades)

        assert metrics["total_trades"] == 2
        assert metrics["winning_trades"] == 1
        assert metrics["losing_trades"] == 1
        assert metrics["win_rate"] == 50.0

    def test_win_metrics_empty(self):
        """Test win metrics with no trades."""
        metrics = PortfolioAnalyzer.calculate_win_metrics([])

        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0

    def test_win_metrics_all_winners(self, winning_trade):
        """Test win metrics with all profitable trades."""
        trades = [winning_trade, winning_trade]
        metrics = PortfolioAnalyzer.calculate_win_metrics(trades)

        assert metrics["total_trades"] == 2
        assert metrics["winning_trades"] == 2
        assert metrics["losing_trades"] == 0
        assert metrics["win_rate"] == 100.0

    def test_profit_metrics_mixed(self, winning_trade, losing_trade):
        """Test profit metrics with mixed trades."""
        trades = [winning_trade, losing_trade]
        metrics = PortfolioAnalyzer.calculate_profit_metrics(trades)

        assert metrics["gross_profit"] == pytest.approx(123.456, rel=1e-3)
        assert metrics["gross_loss"] == pytest.approx(50.0, rel=1e-3)
        assert metrics["total_pnl"] == pytest.approx(73.456, rel=1e-2)
        # Profit factor = 123.456 / 50 = 2.47
        assert metrics["profit_factor"] == pytest.approx(2.47, rel=1e-2)

    def test_profit_factor_no_losses(self, winning_trade):
        """Test profit factor when no losing trades."""
        trades = [winning_trade]
        metrics = PortfolioAnalyzer.calculate_profit_metrics(trades)

        # All profit, no loss
        assert metrics["profit_factor"] == pytest.approx(123.456, rel=1e-2)

    def test_payoff_ratio(self, winning_trade, losing_trade):
        """Test payoff ratio (avg win / avg loss)."""
        trades = [winning_trade, losing_trade]
        metrics = PortfolioAnalyzer.calculate_profit_metrics(trades)

        # avg_win = 123.456, avg_loss = 50
        # payoff = 123.456 / 50 = 2.47
        assert metrics["payoff_ratio"] == pytest.approx(2.47, rel=1e-2)

    def test_return_metrics(self, winning_trade, losing_trade):
        """Test return metrics."""
        trades = [winning_trade, losing_trade]
        metrics = PortfolioAnalyzer.calculate_return_metrics(trades, initial_capital=10000.0)

        total_pnl = 123.456 - 50.0  # 73.456
        assert metrics["total_return"] == pytest.approx(73.456, rel=1e-2)
        # ROI = 73.456 / 10000 * 100 = 0.73%
        assert metrics["return_pct"] == pytest.approx(0.73, rel=1e-2)

    def test_duration_metrics(self, winning_trade, losing_trade):
        """Test trade duration metrics."""
        trades = [winning_trade, losing_trade]
        metrics = PortfolioAnalyzer.calculate_duration_metrics(trades)

        assert metrics["avg_duration_hours"] > 0
        assert metrics["min_duration_hours"] <= metrics["avg_duration_hours"]
        assert metrics["max_duration_hours"] >= metrics["avg_duration_hours"]

    def test_best_worst_trades(self, winning_trade, losing_trade):
        """Test best/worst trade identification."""
        trades = [winning_trade, losing_trade]
        metrics = PortfolioAnalyzer.calculate_best_worst_trades(trades)

        assert metrics["best_trade"]["id"] == 1
        assert metrics["best_trade"]["pnl"] == pytest.approx(123.456, rel=1e-3)
        assert metrics["worst_trade"]["id"] == 2
        assert metrics["worst_trade"]["pnl"] == pytest.approx(-50.0, rel=1e-3)


# ============================================================================
# Tests: DrawdownAnalyzer
# ============================================================================


class TestDrawdownAnalyzer:
    """Test drawdown and equity curve analysis."""

    def test_no_drawdown_all_wins(self, winning_trade):
        """Test drawdown calculation when all trades winning."""
        trades = [winning_trade]
        dd = DrawdownAnalyzer.calculate_drawdown(trades, initial_capital=10000.0)

        assert dd["max_drawdown_pct"] == 0.0
        assert dd["max_drawdown_usd"] == 0.0

    def test_drawdown_with_loss(self, winning_trade, losing_trade):
        """Test drawdown calculation with losing trade."""
        # Order: first win (+123.456), then loss (-50)
        trades = [winning_trade, losing_trade]
        dd = DrawdownAnalyzer.calculate_drawdown(trades, initial_capital=10000.0)

        # After first trade: 10000 + 123.456 = 10123.456 (new peak)
        # After second trade: 10123.456 - 50 = 10073.456
        # Drawdown from peak = 50 USDT
        assert dd["max_drawdown_usd"] == pytest.approx(50.0, rel=1e-2)

    def test_recovery_factor(self, winning_trade, losing_trade):
        """Test recovery factor calculation."""
        trades = [winning_trade, losing_trade]
        recovery = DrawdownAnalyzer.calculate_recovery_factor(trades, initial_capital=10000.0)

        # Recovery = total_profit / max_drawdown
        # = (123.456 - 50) / 50 = 1.47
        assert recovery == pytest.approx(1.47, rel=1e-2)

    def test_recovery_factor_no_drawdown(self, winning_trade):
        """Test recovery factor when no drawdown."""
        trades = [winning_trade]
        recovery = DrawdownAnalyzer.calculate_recovery_factor(trades, initial_capital=10000.0)

        assert recovery == 0.0  # No drawdown = 0 recovery factor


# ============================================================================
# Tests: StatisticalAnalyzer
# ============================================================================


class TestStatisticalAnalyzer:
    """Test statistical metrics."""

    def test_sharpe_ratio_single_trade(self, winning_trade):
        """Test Sharpe ratio with single trade."""
        trades = [winning_trade]
        sharpe = StatisticalAnalyzer.calculate_sharpe_ratio(trades, initial_capital=10000.0)

        # Single trade: can't calculate stdev
        assert sharpe == 0.0

    def test_sharpe_ratio_multiple_trades(self, winning_trade, losing_trade):
        """Test Sharpe ratio with multiple trades."""
        trades = [winning_trade, losing_trade]
        sharpe = StatisticalAnalyzer.calculate_sharpe_ratio(trades, initial_capital=10000.0)

        # Should calculate positive Sharpe (more wins than losses)
        assert sharpe > 0

    def test_sortino_ratio_multiple_trades(self, winning_trade, losing_trade):
        """Test Sortino ratio (penalizes downside volatility only)."""
        trades = [winning_trade, losing_trade]
        sortino = StatisticalAnalyzer.calculate_sortino_ratio(trades, initial_capital=10000.0)

        # Sortino is a valid ratio (can be higher or lower than Sharpe depending on volatility distribution)
        # Just verify it's calculated without error and is numeric
        assert isinstance(sortino, (int, float))
        assert not (math.isnan(sortino) or math.isinf(sortino))

    def test_calmar_ratio_multiple_trades(self, winning_trade, losing_trade):
        """Test Calmar ratio (return / max drawdown)."""
        trades = [winning_trade, losing_trade]
        calmar = StatisticalAnalyzer.calculate_calmar_ratio(trades, initial_capital=10000.0)

        # Calmar = annual_return / max_drawdown%
        # Should be positive
        assert calmar >= 0

    def test_statistics_with_no_trades(self):
        """Test statistics with empty trade list."""
        sharpe = StatisticalAnalyzer.calculate_sharpe_ratio([], initial_capital=10000.0)
        sortino = StatisticalAnalyzer.calculate_sortino_ratio([], initial_capital=10000.0)
        calmar = StatisticalAnalyzer.calculate_calmar_ratio([], initial_capital=10000.0)

        assert sharpe == 0.0
        assert sortino == 0.0
        assert calmar == 0.0


# ============================================================================
# Tests: Report Generation
# ============================================================================


class TestPerformanceReportGenerator:
    """Test report generation."""

    @pytest.mark.asyncio
    async def test_report_generation(self, db, winning_trade, losing_trade):
        """Test complete report generation."""
        # Add trades to database
        db.add(winning_trade)
        db.add(losing_trade)
        db.commit()

        # Mock repository
        with patch("performance_analytics.TradeRepository") as mock_repo:
            mock_repo.get_user_trades.return_value = [winning_trade, losing_trade]

            report = await PerformanceReportGenerator.generate_report(
                db=db,
                user_id="test_user",
                initial_capital=10000.0,
            )

        assert report["user_id"] == "test_user"
        assert report["summary"]["total_trades"] == 2
        assert "wins_losses" in report
        assert "profits" in report
        assert "returns" in report
        assert "duration" in report
        assert "drawdown" in report
        assert "statistics" in report

    @pytest.mark.asyncio
    async def test_report_with_date_filters(self, db, winning_trade, losing_trade):
        """Test report generation with date filtering."""
        db.add(winning_trade)
        db.add(losing_trade)
        db.commit()

        start_date = datetime.utcnow() - timedelta(days=2)
        end_date = datetime.utcnow()

        with patch("performance_analytics.TradeRepository") as mock_repo:
            mock_repo.get_user_trades.return_value = [winning_trade, losing_trade]

            report = await PerformanceReportGenerator.generate_report(
                db=db,
                user_id="test_user",
                initial_capital=10000.0,
                start_date=start_date,
                end_date=end_date,
            )

        assert report["period"]["start_date"] is not None
        assert report["period"]["end_date"] is not None


# ============================================================================
# Tests: Integration Scenarios
# ============================================================================


class TestPerformanceAnalyticsIntegration:
    """Test complex performance analysis scenarios."""

    def test_portfolio_analysis_realistic(self):
        """Test portfolio analysis with realistic trading sequence."""
        # Create a realistic trading sequence
        trades = []

        # Day 1: Win +100
        t1 = TradeDB(
            user_id="user1", symbol="BTC", direction="LONG",
            entry_price=40000, exit_price=41000, quantity=0.1, exit_quantity=0.1,
            entry_value=4000,
            order_id="1", status=TradeStatus.CLOSED.value,
            entry_timestamp=datetime(2026, 1, 1),
            exit_timestamp=datetime(2026, 1, 1, 4),
            realized_pnl=100.0, realized_pnl_pct=2.5,
            stop_loss=39000, take_profit_1=42000, fees=0
        )
        trades.append(t1)

        # Day 2: Loss -30
        t2 = TradeDB(
            user_id="user1", symbol="ETH", direction="SHORT",
            entry_price=2500, exit_price=2530, quantity=1.0, exit_quantity=1.0,
            entry_value=2500,
            order_id="2", status=TradeStatus.CLOSED.value,
            entry_timestamp=datetime(2026, 1, 2),
            exit_timestamp=datetime(2026, 1, 2, 8),
            realized_pnl=-30.0, realized_pnl_pct=-1.2,
            stop_loss=2600, take_profit_1=2400, fees=0
        )
        trades.append(t2)

        # Day 3: Win +30
        t3 = TradeDB(
            user_id="user1", symbol="BNB", direction="LONG",
            entry_price=500, exit_price=530, quantity=1.0, exit_quantity=1.0,
            entry_value=500,
            order_id="3", status=TradeStatus.CLOSED.value,
            entry_timestamp=datetime(2026, 1, 3),
            exit_timestamp=datetime(2026, 1, 3, 10),
            realized_pnl=30.0, realized_pnl_pct=6.0,
            stop_loss=490, take_profit_1=510, fees=0
        )
        trades.append(t3)

        # Analyze portfolio
        initial_capital = 10000.0

        wins = PortfolioAnalyzer.calculate_win_metrics(trades)
        assert wins["total_trades"] == 3
        assert wins["winning_trades"] == 2
        assert wins["win_rate"] == pytest.approx(66.67, rel=1e-2)

        profits = PortfolioAnalyzer.calculate_profit_metrics(trades)
        assert profits["gross_profit"] == pytest.approx(130.0, rel=1e-2)  # 100 + 30
        assert profits["gross_loss"] == pytest.approx(30.0, rel=1e-2)
        assert profits["profit_factor"] == pytest.approx(4.33, rel=1e-2)

        returns = PortfolioAnalyzer.calculate_return_metrics(trades, initial_capital)
        assert returns["total_return"] == pytest.approx(100.0, rel=1e-2)  # 100 - 30 + 30
        assert returns["return_pct"] == pytest.approx(1.0, rel=1e-2)  # 100/10000

    def test_sharpe_sortino_comparison(self):
        """Test that both Sharpe and Sortino ratios are calculated properly."""
        # Profitable trades have high upside, few downsides
        win1 = TradeDB(
            user_id="user1", symbol="BTC", direction="LONG",
            entry_price=10000, exit_price=10200, quantity=0.1, exit_quantity=0.1,
            entry_value=1000, order_id="1",
            realized_pnl=20.0, realized_pnl_pct=2.0,
            stop_loss=9900, take_profit_1=10500,
            status=TradeStatus.CLOSED.value,
            entry_timestamp=datetime.now(), exit_timestamp=datetime.now()
        )
        win2 = TradeDB(
            user_id="user1", symbol="ETH", direction="LONG",
            entry_price=10200, exit_price=10353, quantity=0.1, exit_quantity=0.1,
            entry_value=1020, order_id="2",
            realized_pnl=15.3, realized_pnl_pct=1.5,
            stop_loss=10100, take_profit_1=10700,
            status=TradeStatus.CLOSED.value,
            entry_timestamp=datetime.now(), exit_timestamp=datetime.now()
        )
        loss1 = TradeDB(
            user_id="user1", symbol="ADA", direction="LONG",
            entry_price=10353, exit_price=10300, quantity=0.1, exit_quantity=0.1,
            entry_value=1035, order_id="3",
            realized_pnl=-5.3, realized_pnl_pct=-0.5,
            stop_loss=10450, take_profit_1=10700,
            status=TradeStatus.CLOSED.value,
            entry_timestamp=datetime.now(), exit_timestamp=datetime.now()
        )

        trades = [win1, win2, loss1]
        capital = 10000.0

        sharpe = StatisticalAnalyzer.calculate_sharpe_ratio(trades, capital)
        sortino = StatisticalAnalyzer.calculate_sortino_ratio(trades, capital)

        # Both should be valid numeric values
        assert isinstance(sharpe, (int, float))
        assert isinstance(sortino, (int, float))
        assert sharpe >= 0  # Sharpe for profitable trades should be positive
        assert sortino >= 0  # Sortino for profitable trades should be positive
