"""
Unit tests for drawdown recovery protocol.

Tests cover:
- Drawdown calculation from trade history
- Recovery state determination (ACTIVE, CAUTION, RECOVERY, PAUSED)
- Position size reduction during recovery
- Signal filtering based on confidence and recovery state
- Consecutive win/loss streak counting
- Recovery progress tracking
"""

import pytest
from datetime import datetime, timedelta
from drawdown_recovery import (
    DrawdownCalculator,
    RecoveryProtocol,
    RecoveryState,
    DrawdownMetrics,
)


class TestDrawdownCalculator:
    """Tests for drawdown metric calculation."""

    def test_no_trades_zero_drawdown(self):
        """Empty trade history should have zero drawdown."""
        metrics = DrawdownCalculator.calculate_metrics([], 50000.0)

        assert metrics.current_balance == 50000.0
        assert metrics.peak_balance == 50000.0
        assert metrics.current_drawdown_pct == 0.0
        assert metrics.max_drawdown_pct == 0.0
        assert metrics.consecutive_losses == 0
        assert metrics.consecutive_wins == 0

    def test_winning_trades_no_drawdown(self):
        """Only profitable trades should have zero drawdown."""
        trades = [
            {
                "pnl": 500.0,
                "pnl_pct": 1.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=2),
                "exit_timestamp": datetime.utcnow() - timedelta(hours=1),
            },
            {
                "pnl": 750.0,
                "pnl_pct": 1.5,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=1),
                "exit_timestamp": datetime.utcnow(),
            },
        ]

        metrics = DrawdownCalculator.calculate_metrics(trades, 51250.0)

        assert metrics.current_drawdown_pct == 0.0
        assert metrics.max_drawdown_pct == 0.0
        assert metrics.consecutive_wins == 2

    def test_single_losing_trade_creates_drawdown(self):
        """Single loss from peak creates measurable drawdown."""
        trades = [
            {
                "pnl": -1000.0,
                "pnl_pct": -2.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=1),
                "exit_timestamp": datetime.utcnow(),
            }
        ]

        metrics = DrawdownCalculator.calculate_metrics(trades, 49000.0)

        assert metrics.current_drawdown_pct == pytest.approx(2.0, rel=1e-2)
        assert metrics.consecutive_losses == 1

    def test_recovery_from_drawdown(self):
        """Drawdown should reduce when balance recovers."""
        trades = [
            {
                "pnl": -1000.0,
                "pnl_pct": -2.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=2),
                "exit_timestamp": datetime.utcnow() - timedelta(hours=1),
            },
            {
                "pnl": 1500.0,
                "pnl_pct": 3.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=1),
                "exit_timestamp": datetime.utcnow(),
            },
        ]

        metrics = DrawdownCalculator.calculate_metrics(trades, 50500.0)

        # Peak was $50k, current is $50.5k, so 0% drawdown
        assert metrics.current_drawdown_pct == pytest.approx(0.0, abs=0.1)

    def test_max_drawdown_tracking(self):
        """Should track the worst drawdown point."""
        trades = [
            {
                "pnl": -2000.0,
                "pnl_pct": -4.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=3),
                "exit_timestamp": datetime.utcnow() - timedelta(hours=2),
            },
            {
                "pnl": -1000.0,
                "pnl_pct": -2.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=2),
                "exit_timestamp": datetime.utcnow() - timedelta(hours=1),
            },
            {
                "pnl": 1500.0,
                "pnl_pct": 3.0,
                "entry_timestamp": datetime.utcnow() - timedelta(hours=1),
                "exit_timestamp": datetime.utcnow(),
            },
        ]

        metrics = DrawdownCalculator.calculate_metrics(trades, 48500.0)

        # Max drawdown should be 6% (from 50k to 47k after 2 losses)
        assert metrics.max_drawdown_pct == pytest.approx(6.0, rel=1e-2)

    def test_consecutive_wins_count(self):
        """Count trailing consecutive winning trades."""
        trades = [
            {"pnl": 500, "pnl_pct": 1.0},
            {"pnl": -200, "pnl_pct": -0.4},
            {"pnl": 600, "pnl_pct": 1.2},
            {"pnl": 800, "pnl_pct": 1.6},
        ]

        metrics = DrawdownCalculator.calculate_metrics(trades, 51700.0)

        assert metrics.consecutive_wins == 2  # Last two trades are wins

    def test_consecutive_losses_count(self):
        """Count trailing consecutive losing trades."""
        trades = [
            {"pnl": 500, "pnl_pct": 1.0},
            {"pnl": -200, "pnl_pct": -0.4},
            {"pnl": -300, "pnl_pct": -0.6},
            {"pnl": -100, "pnl_pct": -0.2},
        ]

        metrics = DrawdownCalculator.calculate_metrics(trades, 49900.0)

        assert metrics.consecutive_losses == 3  # Last three trades are losses

    def test_recovery_target_calculation(self):
        """Recovery target should be 95% of peak."""
        trades = [
            {"pnl": -2000.0, "pnl_pct": -4.0}
        ]

        metrics = DrawdownCalculator.calculate_metrics(trades, 48000.0)

        # Peak = 50k, recovery target = 50k * 0.95 = 47.5k
        assert metrics.recovery_target == pytest.approx(47500.0, rel=1e-2)


class TestRecoveryProtocol:
    """Tests for recovery state determination and actions."""

    def test_active_state_zero_drawdown(self):
        """Zero drawdown should be ACTIVE state."""
        state = RecoveryProtocol.get_state(0.0)
        assert state == RecoveryState.ACTIVE

    def test_active_state_up_to_5_percent(self):
        """Drawdown <5% should be ACTIVE state."""
        state = RecoveryProtocol.get_state(4.5)
        assert state == RecoveryState.ACTIVE

    def test_caution_state_5_to_15_percent(self):
        """Drawdown 5-15% should be CAUTION state."""
        state = RecoveryProtocol.get_state(10.0)
        assert state == RecoveryState.CAUTION

    def test_recovery_state_15_to_25_percent(self):
        """Drawdown 15-25% should be RECOVERY state."""
        state = RecoveryProtocol.get_state(20.0)
        assert state == RecoveryState.RECOVERY

    def test_paused_state_above_25_percent(self):
        """Drawdown >25% should be PAUSED state."""
        state = RecoveryProtocol.get_state(30.0)
        assert state == RecoveryState.PAUSED

    def test_active_action_allows_all_trades(self):
        """ACTIVE state should allow all signals."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=49900.0,
            current_drawdown_pct=0.2,
            max_drawdown_pct=0.2,
            drawdown_duration_hours=1.0,
            consecutive_losses=0,
            consecutive_wins=1,
            recovery_target=47500.0,
        )

        action = RecoveryProtocol.get_action(metrics)

        assert action.state == RecoveryState.ACTIVE
        assert action.allow_trading is True
        assert action.position_size_multiplier == 1.0
        assert action.min_confidence_required == "LOW"

    def test_caution_action_reduces_position(self):
        """CAUTION state should reduce position size 25%."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=43000.0,
            current_drawdown_pct=14.0,
            max_drawdown_pct=14.0,
            drawdown_duration_hours=2.0,
            consecutive_losses=1,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        action = RecoveryProtocol.get_action(metrics)

        assert action.state == RecoveryState.CAUTION
        assert action.allow_trading is True
        assert action.position_size_multiplier == 0.75
        assert action.min_confidence_required == "HIGH"

    def test_recovery_action_strict_requirements(self):
        """RECOVERY state should require VERY_HIGH confidence only."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=39000.0,
            current_drawdown_pct=22.0,
            max_drawdown_pct=22.0,
            drawdown_duration_hours=5.0,
            consecutive_losses=3,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        action = RecoveryProtocol.get_action(metrics)

        assert action.state == RecoveryState.RECOVERY
        assert action.allow_trading is True
        assert action.position_size_multiplier == 0.5
        assert action.min_confidence_required == "VERY_HIGH"

    def test_paused_action_stops_all_trades(self):
        """PAUSED state should stop all trading."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=36000.0,
            current_drawdown_pct=28.0,
            max_drawdown_pct=28.0,
            drawdown_duration_hours=8.0,
            consecutive_losses=5,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        action = RecoveryProtocol.get_action(metrics)

        assert action.state == RecoveryState.PAUSED
        assert action.allow_trading is False
        assert action.position_size_multiplier == 0.0

    def test_should_skip_signal_on_pause(self):
        """PAUSED state should skip all signals regardless of confidence."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=35000.0,
            current_drawdown_pct=30.0,
            max_drawdown_pct=30.0,
            drawdown_duration_hours=10.0,
            consecutive_losses=6,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        # Even VERY_HIGH confidence signal should be skipped
        assert RecoveryProtocol.should_skip_signal("VERY_HIGH", metrics) is True

    def test_should_skip_low_confidence_in_recovery(self):
        """RECOVERY state should skip signals below VERY_HIGH."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=39000.0,
            current_drawdown_pct=22.0,
            max_drawdown_pct=22.0,
            drawdown_duration_hours=5.0,
            consecutive_losses=3,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        assert RecoveryProtocol.should_skip_signal("MEDIUM", metrics) is True
        assert RecoveryProtocol.should_skip_signal("HIGH", metrics) is True
        assert RecoveryProtocol.should_skip_signal("VERY_HIGH", metrics) is False

    def test_should_skip_low_confidence_in_caution(self):
        """CAUTION state should skip signals below HIGH."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=43000.0,
            current_drawdown_pct=14.0,
            max_drawdown_pct=14.0,
            drawdown_duration_hours=2.0,
            consecutive_losses=2,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        assert RecoveryProtocol.should_skip_signal("MEDIUM", metrics) is True
        assert RecoveryProtocol.should_skip_signal("HIGH", metrics) is False
        assert RecoveryProtocol.should_skip_signal("VERY_HIGH", metrics) is False

    def test_position_reduction_active_state(self):
        """ACTIVE state should not reduce position size."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=49500.0,
            current_drawdown_pct=1.0,
            max_drawdown_pct=1.0,
            drawdown_duration_hours=0.5,
            consecutive_losses=0,
            consecutive_wins=1,
            recovery_target=47500.0,
        )

        reduced_size = RecoveryProtocol.calculate_position_reduction(1000.0, metrics)

        assert reduced_size == pytest.approx(1000.0, rel=1e-6)

    def test_position_reduction_caution_state(self):
        """CAUTION state should reduce position 25%."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=43000.0,
            current_drawdown_pct=14.0,
            max_drawdown_pct=14.0,
            drawdown_duration_hours=2.0,
            consecutive_losses=1,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        reduced_size = RecoveryProtocol.calculate_position_reduction(1000.0, metrics)

        assert reduced_size == pytest.approx(750.0, rel=1e-6)

    def test_position_reduction_recovery_state(self):
        """RECOVERY state should reduce position 50%."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=39000.0,
            current_drawdown_pct=22.0,
            max_drawdown_pct=22.0,
            drawdown_duration_hours=5.0,
            consecutive_losses=3,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        reduced_size = RecoveryProtocol.calculate_position_reduction(1000.0, metrics)

        assert reduced_size == pytest.approx(500.0, rel=1e-6)

    def test_position_reduction_paused_state(self):
        """PAUSED state should eliminate position size."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=35000.0,
            current_drawdown_pct=30.0,
            max_drawdown_pct=30.0,
            drawdown_duration_hours=10.0,
            consecutive_losses=6,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        reduced_size = RecoveryProtocol.calculate_position_reduction(1000.0, metrics)

        assert reduced_size == 0.0

    def test_recovery_status_reporting(self):
        """Recovery status should provide complete diagnostic information."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=41000.0,
            current_drawdown_pct=18.0,
            max_drawdown_pct=18.0,
            drawdown_duration_hours=4.0,
            consecutive_losses=2,
            consecutive_wins=0,
            recovery_target=47500.0,
        )

        status = RecoveryProtocol.get_recovery_status(metrics)

        assert status["state"] == "RECOVERY"
        assert status["current_drawdown_pct"] == 18.0
        assert status["peak_balance"] == 50000.0
        assert status["current_balance"] == 41000.0
        assert status["recovery_target"] == 47500.0
        assert status["balance_to_recover"] == pytest.approx(6500.0, rel=1e-2)
        assert status["allow_trading"] is True
        assert status["position_size_multiplier"] == 0.5
        assert status["min_confidence_required"] == "VERY_HIGH"
        assert status["consecutive_losses"] == 2
        assert status["consecutive_wins"] == 0

    def test_recovery_progress_calculation(self):
        """Recovery progress should measure distance to recovery target."""
        metrics = DrawdownMetrics(
            peak_balance=50000.0,
            current_balance=47500.0,
            current_drawdown_pct=5.0,
            max_drawdown_pct=20.0,
            drawdown_duration_hours=3.0,
            consecutive_losses=0,
            consecutive_wins=1,
            recovery_target=47500.0,
        )

        status = RecoveryProtocol.get_recovery_status(metrics)

        # At recovery target = 100% progress
        assert status["recovery_progress_pct"] == pytest.approx(100.0, rel=1e-2)
