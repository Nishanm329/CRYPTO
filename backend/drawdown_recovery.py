"""
Drawdown Recovery Protocol.

Prevents over-trading during losing streaks and enforces strict recovery mode:
- Automatic pause when drawdown exceeds threshold (15%, 20%, 25%)
- Recovery mode: Only execute trades with confidence >= VERY_HIGH (85+)
- Gradual re-engagement: Reduce position size 50% in recovery mode
- Auto-resume: Exit recovery when drawdown recovers to <5%
- Streak tracking: Monitor consecutive losses/wins to detect risky patterns

States:
- ACTIVE: Normal trading, all confidence levels accepted
- RECOVERY: Drawdown >threshold, accept only VERY_HIGH confidence
- PAUSED: Drawdown >30%, all trading stopped

Drawdown thresholds:
- 5-15%: Warning level, normal trading continues
- 15-20%: Caution level, position sizes reduced 25%
- 20-25%: Recovery mode, only VERY_HIGH signals accepted
- >25%: Pause mode, trading disabled
- Recovery: <5% from peak exits recovery mode
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RecoveryState(str, Enum):
    """Trading state during drawdown recovery."""
    ACTIVE = "ACTIVE"
    CAUTION = "CAUTION"
    RECOVERY = "RECOVERY"
    PAUSED = "PAUSED"


@dataclass
class DrawdownMetrics:
    """Drawdown tracking metrics."""
    peak_balance: float  # Highest balance reached
    current_balance: float  # Current account balance
    current_drawdown_pct: float  # Current drawdown as % (0-100)
    max_drawdown_pct: float  # Worst drawdown in session
    drawdown_duration_hours: float  # Time in drawdown
    consecutive_losses: int  # Trades in a row that lost money
    consecutive_wins: int  # Trades in a row that made money
    recovery_target: float  # Balance needed to exit recovery mode
    last_trade_timestamp: Optional[datetime] = None
    entered_recovery_timestamp: Optional[datetime] = None


@dataclass
class RecoveryAction:
    """Action to take based on recovery state."""
    state: RecoveryState
    allow_trading: bool
    position_size_multiplier: float  # How much to reduce positions
    min_confidence_required: str  # Min rating to trade (VERY_HIGH, HIGH, etc)
    description: str
    recommendation: str


class DrawdownCalculator:
    """Calculates drawdown metrics from trade history."""

    @staticmethod
    def calculate_metrics(
        trades: List[Dict],
        current_balance: float,
    ) -> DrawdownMetrics:
        """
        Calculate drawdown metrics from closed trades.

        Args:
            trades: List of closed trades with entry/exit prices and P&L
            current_balance: Current account balance

        Returns:
            DrawdownMetrics object with all relevant metrics
        """
        if not trades:
            return DrawdownMetrics(
                peak_balance=current_balance,
                current_balance=current_balance,
                current_drawdown_pct=0.0,
                max_drawdown_pct=0.0,
                drawdown_duration_hours=0.0,
                consecutive_losses=0,
                consecutive_wins=0,
                recovery_target=current_balance,
            )

        # Reconstruct balance progression
        starting_balance = current_balance - sum(
            t.get("pnl", 0) for t in trades
        )
        peak_balance = starting_balance
        balances = [starting_balance]
        current = starting_balance

        for trade in trades:
            current += trade.get("pnl", 0)
            balances.append(current)
            peak_balance = max(peak_balance, current)

        # Calculate current drawdown
        current_drawdown_pct = (
            ((peak_balance - current_balance) / peak_balance) * 100
            if peak_balance > 0
            else 0.0
        )

        # Calculate max drawdown (worst point from any peak)
        max_dd = 0.0
        running_peak = starting_balance
        for balance in balances:
            running_peak = max(running_peak, balance)
            dd = ((running_peak - balance) / running_peak) * 100 if running_peak > 0 else 0.0
            max_dd = max(max_dd, dd)

        # Drawdown duration and first loss timestamp
        drawdown_hours = 0.0
        entered_recovery_timestamp = None
        first_loss_idx = None

        for i in range(1, len(balances)):
            if balances[i] < peak_balance:
                first_loss_idx = i - 1  # Trade index (balances has one extra element)
                break

        if first_loss_idx is not None and first_loss_idx < len(trades):
            first_loss_time = trades[first_loss_idx].get("entry_timestamp")
            last_time = trades[-1].get("exit_timestamp", datetime.utcnow())
            entered_recovery_timestamp = first_loss_time
            if first_loss_time and last_time:
                drawdown_hours = (last_time - first_loss_time).total_seconds() / 3600

        # Consecutive wins/losses
        consecutive_wins = DrawdownCalculator._count_consecutive(trades, True)
        consecutive_losses = DrawdownCalculator._count_consecutive(trades, False)

        # Recovery target: 95% of peak balance (5% buffer)
        recovery_target = peak_balance * 0.95

        return DrawdownMetrics(
            peak_balance=peak_balance,
            current_balance=current_balance,
            current_drawdown_pct=current_drawdown_pct,
            max_drawdown_pct=max_dd,
            drawdown_duration_hours=drawdown_hours,
            consecutive_losses=consecutive_losses,
            consecutive_wins=consecutive_wins,
            recovery_target=recovery_target,
            last_trade_timestamp=trades[-1].get("exit_timestamp") if trades else None,
            entered_recovery_timestamp=entered_recovery_timestamp,
        )

    @staticmethod
    def _count_consecutive(trades: List[Dict], winning: bool) -> int:
        """Count trailing consecutive wins or losses."""
        if not trades:
            return 0
        count = 0
        for trade in reversed(trades):
            pnl_pct = trade.get("pnl_pct", 0)
            is_win = pnl_pct > 0
            if (winning and is_win) or (not winning and not is_win):
                count += 1
            else:
                break
        return count


class RecoveryProtocol:
    """Manages trading during drawdown recovery."""

    # Drawdown thresholds and actions
    THRESHOLDS = {
        0: ("ACTIVE", True, 1.0, None),  # 0-5%: Normal trading
        5: ("CAUTION", True, 0.75, None),  # 5-15%: Reduce size 25%
        15: ("RECOVERY", True, 0.5, "VERY_HIGH"),  # 15-25%: Reduce size 50%, high confidence only
        25: ("PAUSED", False, 0.0, None),  # >25%: Pause all trading
    }

    @staticmethod
    def get_state(drawdown_pct: float) -> RecoveryState:
        """Determine recovery state from drawdown percentage."""
        if drawdown_pct < 5:
            return RecoveryState.ACTIVE
        elif drawdown_pct < 15:
            return RecoveryState.CAUTION
        elif drawdown_pct < 25:
            return RecoveryState.RECOVERY
        else:
            return RecoveryState.PAUSED

    @staticmethod
    def get_action(
        metrics: DrawdownMetrics,
        consecutive_losses: int = 0,
    ) -> RecoveryAction:
        """
        Determine trading action based on drawdown metrics.

        Args:
            metrics: Drawdown metrics
            consecutive_losses: Current streak of losses (for enhanced caution)

        Returns:
            RecoveryAction with state and constraints
        """
        state = RecoveryProtocol.get_state(metrics.current_drawdown_pct)

        if state == RecoveryState.ACTIVE:
            return RecoveryAction(
                state=RecoveryState.ACTIVE,
                allow_trading=True,
                position_size_multiplier=1.0,
                min_confidence_required="LOW",
                description="Account in profit or <5% drawdown",
                recommendation="Normal trading: all signal confidence levels accepted",
            )

        elif state == RecoveryState.CAUTION:
            # Extra penalty if consecutive losses
            multiplier = 0.75 if consecutive_losses < 2 else 0.5
            return RecoveryAction(
                state=RecoveryState.CAUTION,
                allow_trading=True,
                position_size_multiplier=multiplier,
                min_confidence_required="HIGH",
                description=f"Drawdown {metrics.current_drawdown_pct:.1f}% (5-15%)",
                recommendation=f"Caution mode: Position size reduced {(1-multiplier)*100:.0f}%, HIGH+ confidence only",
            )

        elif state == RecoveryState.RECOVERY:
            # Even stricter: 50% position size, VERY_HIGH only
            return RecoveryAction(
                state=RecoveryState.RECOVERY,
                allow_trading=True,
                position_size_multiplier=0.5,
                min_confidence_required="VERY_HIGH",
                description=f"Drawdown {metrics.current_drawdown_pct:.1f}% (15-25%)",
                recommendation="Recovery mode: Position size reduced 50%, VERY_HIGH confidence signals only",
            )

        else:  # PAUSED
            return RecoveryAction(
                state=RecoveryState.PAUSED,
                allow_trading=False,
                position_size_multiplier=0.0,
                min_confidence_required="PERFECT",
                description=f"Drawdown {metrics.current_drawdown_pct:.1f}% (>25%)",
                recommendation="Pause mode: All new trades disabled. Exit recovery when drawdown < 5%",
            )

    @staticmethod
    def should_skip_signal(
        confidence_rating: str,
        metrics: DrawdownMetrics,
    ) -> bool:
        """
        Determine if signal should be skipped due to recovery state.

        Args:
            confidence_rating: Signal confidence rating (VERY_HIGH, HIGH, MEDIUM, etc)
            metrics: Current drawdown metrics

        Returns:
            True if signal should be skipped, False if allowed
        """
        action = RecoveryProtocol.get_action(metrics)

        if not action.allow_trading:
            return True

        # Check if confidence is high enough for current state
        confidence_hierarchy = ["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
        min_required_idx = confidence_hierarchy.index(action.min_confidence_required)
        signal_idx = confidence_hierarchy.index(confidence_rating)

        return signal_idx < min_required_idx

    @staticmethod
    def calculate_position_reduction(
        base_position_size: float,
        metrics: DrawdownMetrics,
    ) -> float:
        """
        Calculate position size reduction based on drawdown.

        Args:
            base_position_size: Original position size in USD
            metrics: Drawdown metrics

        Returns:
            Adjusted position size in USD
        """
        action = RecoveryProtocol.get_action(metrics)
        return base_position_size * action.position_size_multiplier

    @staticmethod
    def get_recovery_status(metrics: DrawdownMetrics) -> Dict[str, any]:
        """
        Get human-readable recovery status.

        Returns:
            Dictionary with status, progress, and guidance
        """
        state = RecoveryProtocol.get_state(metrics.current_drawdown_pct)
        action = RecoveryProtocol.get_action(metrics)

        # Recovery progress
        balance_to_recover = metrics.recovery_target - metrics.current_balance
        recovery_progress = (
            ((metrics.peak_balance - metrics.current_balance) / (metrics.peak_balance - metrics.recovery_target)) * 100
            if metrics.peak_balance > metrics.recovery_target
            else 100.0
        )

        return {
            "state": state.value,
            "current_drawdown_pct": metrics.current_drawdown_pct,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "peak_balance": metrics.peak_balance,
            "current_balance": metrics.current_balance,
            "recovery_target": metrics.recovery_target,
            "balance_to_recover": max(0, balance_to_recover),
            "recovery_progress_pct": min(100.0, max(0, recovery_progress)),
            "consecutive_wins": metrics.consecutive_wins,
            "consecutive_losses": metrics.consecutive_losses,
            "allow_trading": action.allow_trading,
            "position_size_multiplier": action.position_size_multiplier,
            "min_confidence_required": action.min_confidence_required,
            "description": action.description,
            "recommendation": action.recommendation,
        }
