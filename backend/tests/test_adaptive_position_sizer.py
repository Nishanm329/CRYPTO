"""
Unit tests for adaptive position sizing.

Tests cover:
- Signal performance analysis (win rate, profit factor, streaks)
- Position sizing multipliers (confidence, volatility, win rate, streak)
- Constraint enforcement (min 0.5%, max 5% of account)
- Drawdown penalties
- Interpolation accuracy
"""

import pytest
from datetime import datetime, timedelta
from adaptive_position_sizer import (
    AdaptivePositionSizer,
    SignalPerformanceAnalyzer,
    SignalPerformance,
    PositionSizingParams,
)


class TestSignalPerformanceAnalyzer:
    """Tests for analyzing historical signal performance."""

    def test_analyze_winning_signal_type(self):
        """Analyze signal type with high win rate."""
        trades = [
            {
                "symbol": "BTC",
                "timeframe": "1H",
                "direction": "LONG",
                "status": "CLOSED",
                "pnl": 150.0,
                "pnl_pct": 3.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=2),
                "exit_timestamp": datetime.utcnow() - timedelta(hours=1),
            },
            {
                "symbol": "BTC",
                "timeframe": "1H",
                "direction": "LONG",
                "status": "CLOSED",
                "pnl": 200.0,
                "pnl_pct": 4.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=1),
                "exit_timestamp": datetime.utcnow(),
            },
            {
                "symbol": "BTC",
                "timeframe": "1H",
                "direction": "LONG",
                "status": "CLOSED",
                "pnl": -100.0,
                "pnl_pct": -2.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=3),
                "exit_timestamp": datetime.utcnow() - timedelta(hours=2),
            },
        ]

        perf = SignalPerformanceAnalyzer.analyze_signal_type(
            trades, "BTC", "1H", "LONG"
        )

        assert perf is not None
        assert perf.total_trades == 3
        assert perf.winning_trades == 2
        assert perf.losing_trades == 1
        assert perf.win_rate == pytest.approx(0.667, rel=1e-2)
        assert perf.average_win == pytest.approx(3.5, rel=1e-2)
        assert perf.average_loss == pytest.approx(-2.0, rel=1e-2)
        assert perf.profit_factor == pytest.approx(3.5, rel=1e-2)  # 350 / 100
        assert perf.sample_size_adequate is False  # Only 3 trades

    def test_analyze_no_matching_trades(self):
        """Returns None when no trades match signal type."""
        trades = [
            {
                "symbol": "ETH",
                "timeframe": "1H",
                "direction": "SHORT",
                "status": "CLOSED",
                "pnl": 100.0,
            }
        ]

        perf = SignalPerformanceAnalyzer.analyze_signal_type(
            trades, "BTC", "1H", "LONG"
        )

        assert perf is None

    def test_analyze_adequate_sample_size(self):
        """Marks sample as adequate when 10+ trades."""
        trades = [
            {
                "symbol": "BTC",
                "timeframe": "1H",
                "direction": "LONG",
                "status": "CLOSED",
                "pnl": 100.0 if i % 2 == 0 else -50.0,
                "pnl_pct": 2.0 if i % 2 == 0 else -1.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=i),
                "exit_timestamp": datetime.utcnow() - timedelta(hours=i - 1),
            }
            for i in range(1, 11)
        ]

        perf = SignalPerformanceAnalyzer.analyze_signal_type(
            trades, "BTC", "1H", "LONG"
        )

        assert perf is not None
        assert perf.total_trades == 10
        assert perf.sample_size_adequate is True

    def test_consecutive_wins_count(self):
        """Count trailing consecutive wins correctly."""
        trades = [
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": 100, "pnl_pct": 2},
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": 150, "pnl_pct": 3},
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": -50, "pnl_pct": -1},
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": 200, "pnl_pct": 4},
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": 120, "pnl_pct": 2.4},
        ]

        perf = SignalPerformanceAnalyzer.analyze_signal_type(
            trades, "BTC", "1H", "LONG"
        )

        assert perf.consecutive_wins == 2  # Last two trades are wins

    def test_consecutive_losses_count(self):
        """Count trailing consecutive losses correctly."""
        trades = [
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": 100, "pnl_pct": 2},
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": -50, "pnl_pct": -1},
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": -75, "pnl_pct": -1.5},
            {"symbol": "BTC", "timeframe": "1H", "direction": "LONG", "status": "CLOSED", "pnl": -100, "pnl_pct": -2},
        ]

        perf = SignalPerformanceAnalyzer.analyze_signal_type(
            trades, "BTC", "1H", "LONG"
        )

        assert perf.consecutive_losses == 3  # Last three trades are losses


class TestAdaptivePositionSizer:
    """Tests for adaptive position sizing calculation."""

    def test_base_position_sizing(self):
        """Base position calculation from account size and risk %."""
        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params)

        # Base: $50k * 2% = $1000
        assert result.position_value_usd >= 900  # Allow for rounding
        assert result.position_value_pct >= 1.8
        assert result.position_value_pct <= 2.2

    def test_confidence_multiplier_very_high(self):
        """VERY_HIGH confidence (85+) increases position size."""
        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=92.0,  # VERY_HIGH
            signal_rating="VERY_HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params)

        # VERY_HIGH should increase position by ~20%
        assert result.confidence_multiplier > 1.0
        assert result.confidence_multiplier <= 1.5

    def test_confidence_multiplier_low(self):
        """LOW confidence (40-55) decreases position size."""
        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=45.0,  # LOW
            signal_rating="LOW",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params)

        # LOW should reduce position
        assert result.confidence_multiplier < 1.0

    def test_win_rate_multiplier_high_win_rate(self):
        """High historical win rate (70%+) increases position."""
        perf = SignalPerformance(
            signal_key="BTC_1H_LONG",
            total_trades=25,
            winning_trades=18,
            losing_trades=7,
            win_rate=0.72,
            average_win=3.2,
            average_loss=-1.5,
            profit_factor=3.8,
            avg_duration=4.5,
            consecutive_wins=2,
            consecutive_losses=1,
            sample_size_adequate=True,
        )

        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
            win_rate=0.72,
        )

        result = AdaptivePositionSizer.calculate_position_size(params, perf)

        # 72% win rate should get ~1.5x multiplier
        assert result.win_rate_multiplier > 1.0

    def test_win_rate_multiplier_low_win_rate(self):
        """Low historical win rate (40%>) reduces position heavily."""
        perf = SignalPerformance(
            signal_key="BTC_1H_LONG",
            total_trades=15,
            winning_trades=5,
            losing_trades=10,
            win_rate=0.33,
            average_win=2.0,
            average_loss=-3.0,
            profit_factor=0.5,
            avg_duration=3.0,
            consecutive_wins=0,
            consecutive_losses=3,
            sample_size_adequate=True,
        )

        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
            win_rate=0.33,
        )

        result = AdaptivePositionSizer.calculate_position_size(params, perf)

        # 33% win rate should get <1.0x multiplier (heavy reduction)
        assert result.win_rate_multiplier < 1.0

    def test_win_rate_multiplier_insufficient_data(self):
        """Insufficient sample size (< 10 trades) uses neutral 1.0x multiplier."""
        perf = SignalPerformance(
            signal_key="BTC_1H_LONG",
            total_trades=5,  # Insufficient
            winning_trades=3,
            losing_trades=2,
            win_rate=0.6,
            average_win=2.5,
            average_loss=-2.0,
            profit_factor=1.875,
            avg_duration=3.0,
            consecutive_wins=1,
            consecutive_losses=0,
            sample_size_adequate=False,  # Not enough data
        )

        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params, perf)

        # Insufficient data → use neutral 1.0x
        assert result.win_rate_multiplier == 1.0

    def test_volatility_multiplier_low_volatility(self):
        """Low volatility (ATR 0.5) increases position."""
        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=0.5,  # Very low volatility
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params)

        # Low volatility → increase size
        assert result.volatility_multiplier > 1.0

    def test_volatility_multiplier_high_volatility(self):
        """High volatility (ATR 1.5+) reduces position."""
        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.8,  # High volatility
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params)

        # High volatility → reduce size
        assert result.volatility_multiplier < 1.0

    def test_streak_multiplier_winning_streak(self):
        """Winning streak (3+) increases position."""
        perf = SignalPerformance(
            signal_key="BTC_1H_LONG",
            total_trades=10,
            winning_trades=8,
            losing_trades=2,
            win_rate=0.8,
            average_win=3.0,
            average_loss=-2.0,
            profit_factor=4.0,
            avg_duration=4.0,
            consecutive_wins=4,  # 4 wins in a row
            consecutive_losses=0,
            sample_size_adequate=True,
        )

        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params, perf)

        # Winning streak → increase size (1.0 + (4-3)*0.05 = 1.05)
        assert result.streak_multiplier > 1.0

    def test_streak_multiplier_losing_streak(self):
        """Losing streak (2+) reduces position."""
        perf = SignalPerformance(
            signal_key="BTC_1H_LONG",
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
            average_win=2.5,
            average_loss=-2.0,
            profit_factor=1.875,
            avg_duration=3.5,
            consecutive_wins=0,
            consecutive_losses=3,  # 3 losses in a row
            sample_size_adequate=True,
        )

        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params, perf)

        # Losing streak → reduce size
        assert result.streak_multiplier < 1.0

    def test_drawdown_penalty_15_percent(self):
        """15% drawdown applies mild penalty."""
        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(
            params, current_drawdown_pct=15.0
        )

        # 15% drawdown → neutral (no penalty at boundary)
        assert result.position_value_usd > 0

    def test_drawdown_penalty_30_percent(self):
        """30% drawdown applies heavy penalty."""
        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(
            params, current_drawdown_pct=30.0
        )

        # 30% drawdown → (1.0 - (30-15)/50) = 0.7x penalty
        assert result.position_value_usd > 0  # Still positive but reduced

    def test_position_size_respects_minimum(self):
        """Position size cannot go below 0.5% of account."""
        perf = SignalPerformance(
            signal_key="BTC_1H_LONG",
            total_trades=50,
            winning_trades=10,
            losing_trades=40,
            win_rate=0.2,  # Very poor win rate
            average_win=1.0,
            average_loss=-4.0,
            profit_factor=0.25,
            avg_duration=2.0,
            consecutive_wins=0,
            consecutive_losses=5,
            sample_size_adequate=True,
        )

        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=0.1,  # Very small base risk
            confidence_score=40.0,  # LOW confidence
            signal_rating="LOW",
            atr_ratio=2.0,  # High volatility
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(
            params, perf, current_drawdown_pct=25
        )

        # Enforce minimum 0.5%
        min_position = (50000.0 * 0.5) / 100
        assert result.position_value_usd >= min_position

    def test_position_size_respects_maximum(self):
        """Position size cannot exceed 5% of account."""
        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=5.0,  # Maximum base risk
            confidence_score=100.0,  # Perfect confidence
            signal_rating="VERY_HIGH",
            atr_ratio=0.5,  # Very low volatility
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params)

        # Enforce maximum 5%
        max_position = (50000.0 * 5.0) / 100
        assert result.position_value_usd <= max_position

    def test_position_quantity_calculation(self):
        """Position quantity calculated from USD value and entry price."""
        params = PositionSizingParams(
            account_size=100000.0,
            base_risk_pct=2.0,
            confidence_score=70.0,
            signal_rating="HIGH",
            atr_ratio=1.0,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=50000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params)

        # Position value / entry price = quantity
        expected_qty = result.position_value_usd / params.entry_price
        assert result.quantity == pytest.approx(expected_qty, rel=1e-6)

    def test_reasoning_breakdown_comprehensive(self):
        """Verify reasoning dictionary contains all components."""
        perf = SignalPerformance(
            signal_key="BTC_1H_LONG",
            total_trades=15,
            winning_trades=10,
            losing_trades=5,
            win_rate=0.667,
            average_win=3.0,
            average_loss=-2.0,
            profit_factor=3.0,
            avg_duration=4.0,
            consecutive_wins=2,
            consecutive_losses=0,
            sample_size_adequate=True,
        )

        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=75.0,
            signal_rating="HIGH",
            atr_ratio=1.2,
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params, perf)

        # Verify all reasoning components present
        assert "base_position" in result.reasoning
        assert "confidence_factor" in result.reasoning
        assert "win_rate_factor" in result.reasoning
        assert "volatility_factor" in result.reasoning
        assert "streak_factor" in result.reasoning
        assert "drawdown_penalty" in result.reasoning
        assert "final_size" in result.reasoning

    def test_interpolation_accuracy(self):
        """Test multiplier interpolation between thresholds."""
        test_map = {0.4: 0.6, 0.5: 1.0, 0.7: 1.5}

        # At threshold
        result = AdaptivePositionSizer._interpolate_multiplier(0.5, test_map)
        assert result == 1.0

        # Between thresholds: 0.6 is halfway between 0.5 (1.0x) and 0.7 (1.5x)
        result = AdaptivePositionSizer._interpolate_multiplier(0.6, test_map)
        assert result == pytest.approx(1.25, rel=1e-6)  # 1.0 + (1.5-1.0)*0.5

        # Below minimum
        result = AdaptivePositionSizer._interpolate_multiplier(0.3, test_map)
        assert result == 0.6

        # Above maximum
        result = AdaptivePositionSizer._interpolate_multiplier(0.9, test_map)
        assert result == 1.5

    def test_combined_multiplier_effect(self):
        """Test that all multipliers compound correctly."""
        perf = SignalPerformance(
            signal_key="BTC_1H_LONG",
            total_trades=20,
            winning_trades=14,
            losing_trades=6,
            win_rate=0.7,
            average_win=3.5,
            average_loss=-1.5,
            profit_factor=4.0,
            avg_duration=4.5,
            consecutive_wins=3,
            consecutive_losses=0,
            sample_size_adequate=True,
        )

        params = PositionSizingParams(
            account_size=50000.0,
            base_risk_pct=2.0,
            confidence_score=85.0,  # VERY_HIGH
            signal_rating="VERY_HIGH",
            atr_ratio=0.8,  # Low volatility
            symbol="BTC",
            timeframe="1H",
            direction="LONG",
            entry_price=40000.0,
        )

        result = AdaptivePositionSizer.calculate_position_size(params, perf)

        # Verify all multipliers are applied
        assert result.confidence_multiplier > 1.0  # VERY_HIGH confidence
        assert result.win_rate_multiplier > 1.0  # 70% win rate
        assert result.volatility_multiplier > 1.0  # Low volatility
        assert result.streak_multiplier > 1.0  # 3-win streak

        # Final position should reflect compounded effect
        assert result.position_value_pct > 2.0  # More than base 2%
