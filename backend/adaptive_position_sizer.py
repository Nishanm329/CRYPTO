"""
Adaptive Position Sizing Engine.

Learns from signal history to adjust position sizes based on:
- Win rate of signal type (symbol + timeframe)
- Current confidence score
- Account volatility (ATR)
- Risk tolerance
- Consecutive wins/losses (streak adjustment)

Position size multipliers:
Base size × Win Rate Factor × Confidence Factor × Volatility Factor × Streak Factor

Example:
- Base position: $1000 (2% of $50k account)
- BTC 1H signals: 68% win rate → 1.35x multiplier
- Current confidence: VERY_HIGH (score 92) → 1.2x multiplier
- ATR volatility: Low → 1.1x multiplier
- Win streak: +3 → 1.1x multiplier
- Final: $1000 × 1.35 × 1.2 × 1.1 × 1.1 = $1,741 (3.48% of account)

Constraints:
- Min position: 0.5% of account (safety floor)
- Max position: 5% of account (risk ceiling)
- Reduce on losing streak (>2 losses)
- Pause after drawdown >15%
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class SignalType(str, Enum):
    """Signal classification by symbol and timeframe."""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class SignalPerformance:
    """Historical performance metrics for a signal type."""
    signal_key: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    avg_duration: float
    consecutive_wins: int
    consecutive_losses: int
    last_trade_timestamp: Optional[datetime] = None
    sample_size_adequate: bool = False


@dataclass
class PositionSizingParams:
    """Parameters for position sizing calculation."""
    account_size: float
    base_risk_pct: float
    confidence_score: float
    signal_rating: str
    atr_ratio: float
    symbol: str
    timeframe: str
    direction: str
    entry_price: float
    win_rate: Optional[float] = None


@dataclass
class AdaptivePositionSize:
    """Position sizing recommendation."""
    position_value_usd: float
    position_value_pct: float
    quantity: float
    entry_price: float
    confidence_multiplier: float
    win_rate_multiplier: float
    volatility_multiplier: float
    streak_multiplier: float
    reasoning: Dict[str, str]


class SignalPerformanceAnalyzer:
    """Analyzes historical performance of signal types."""

    @staticmethod
    def analyze_signal_type(
        trades: List[Dict],
        symbol: str,
        timeframe: str,
        direction: str,
    ) -> Optional[SignalPerformance]:
        """
        Analyze performance of a specific signal type.

        Args:
            trades: List of closed trades with entry, exit, P&L
            symbol: e.g., "BTC"
            timeframe: e.g., "1H"
            direction: "LONG" or "SHORT"

        Returns:
            SignalPerformance object or None if insufficient data
        """
        signal_key = f"{symbol}_{timeframe}_{direction}"

        # Filter trades for this signal type
        matching_trades = [
            t for t in trades
            if t.get("symbol") == symbol
            and t.get("timeframe") == timeframe
            and t.get("direction") == direction
            and t.get("status") == "CLOSED"
        ]

        if not matching_trades:
            return None

        total = len(matching_trades)
        winning = [t for t in matching_trades if t.get("pnl_pct", 0) > 0]
        losing = [t for t in matching_trades if t.get("pnl_pct", 0) <= 0]

        win_count = len(winning)
        loss_count = len(losing)
        win_rate = win_count / total if total > 0 else 0.0

        # Calculate average wins/losses
        avg_win = (
            sum(t.get("pnl_pct", 0) for t in winning) / win_count
            if win_count > 0
            else 0.0
        )
        avg_loss = (
            sum(t.get("pnl_pct", 0) for t in losing) / loss_count
            if loss_count > 0
            else 0.0
        )

        # Profit factor
        gross_wins = sum(t.get("pnl", 0) for t in winning if t.get("pnl", 0) > 0)
        gross_losses = abs(
            sum(t.get("pnl", 0) for t in losing if t.get("pnl", 0) < 0)
        )
        profit_factor = (
            gross_wins / gross_losses if gross_losses > 0 else 0.0
        )

        # Average duration
        durations = [
            (
                t.get("exit_timestamp", datetime.utcnow())
                - t.get("entry_timestamp", datetime.utcnow())
            ).total_seconds()
            / 3600
            for t in matching_trades
            if t.get("exit_timestamp") and t.get("entry_timestamp")
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # Consecutive wins/losses
        consecutive_wins = SignalPerformanceAnalyzer._count_consecutive_wins(
            matching_trades
        )
        consecutive_losses = SignalPerformanceAnalyzer._count_consecutive_losses(
            matching_trades
        )

        # Last trade timestamp
        last_timestamp = max(
            (t.get("exit_timestamp") for t in matching_trades
             if t.get("exit_timestamp")),
            default=None,
        )

        return SignalPerformance(
            signal_key=signal_key,
            total_trades=total,
            winning_trades=win_count,
            losing_trades=loss_count,
            win_rate=win_rate,
            average_win=avg_win,
            average_loss=avg_loss,
            profit_factor=profit_factor,
            avg_duration=avg_duration,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            last_trade_timestamp=last_timestamp,
            sample_size_adequate=(total >= 10),
        )

    @staticmethod
    def _count_consecutive_wins(trades: List[Dict]) -> int:
        """Count trailing consecutive wins."""
        if not trades:
            return 0
        # Assume trades are sorted by timestamp (newest last)
        count = 0
        for trade in reversed(trades):
            if trade.get("pnl_pct", 0) > 0:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _count_consecutive_losses(trades: List[Dict]) -> int:
        """Count trailing consecutive losses."""
        if not trades:
            return 0
        count = 0
        for trade in reversed(trades):
            if trade.get("pnl_pct", 0) <= 0:
                count += 1
            else:
                break
        return count


class AdaptivePositionSizer:
    """Calculates adaptive position sizes based on multiple factors."""

    # Multiplier ranges
    MIN_POSITION_PCT = 0.5  # Minimum 0.5% of account
    MAX_POSITION_PCT = 5.0  # Maximum 5% of account

    # Win rate multiplier (maps win rate to position multiplier)
    # win_rate < 40% → reduce to 0.6x, 50% → 1.0x, 70% → 1.5x
    WIN_RATE_MULTIPLIER_MAP = {
        0.0: 0.3,   # Losing signal: reduce heavily
        0.4: 0.6,   # Poor: reduce
        0.5: 1.0,   # Break-even: neutral
        0.6: 1.2,   # Good: increase
        0.7: 1.5,   # Excellent: increase more
        0.9: 1.8,   # Exceptional: increase most
    }

    # Confidence score multiplier
    CONFIDENCE_MULTIPLIER_MAP = {
        40: 0.5,    # LOW: very cautious
        55: 0.75,   # MEDIUM: cautious
        70: 1.0,    # HIGH: neutral
        85: 1.2,    # VERY_HIGH: aggressive
        100: 1.5,   # Perfect: most aggressive
    }

    # Volatility multiplier (ATR ratio)
    VOLATILITY_MULTIPLIER_MAP = {
        0.5: 1.5,   # Very low volatility: increase size
        0.8: 1.2,   # Low volatility: increase slightly
        1.0: 1.0,   # Normal volatility: neutral
        1.5: 0.7,   # High volatility: reduce
        2.0: 0.5,   # Very high volatility: reduce heavily
    }

    @staticmethod
    def calculate_position_size(
        params: PositionSizingParams,
        signal_performance: Optional[SignalPerformance] = None,
        current_drawdown_pct: float = 0.0,
    ) -> AdaptivePositionSize:
        """
        Calculate adaptive position size.

        Args:
            params: Positioning parameters (account size, confidence, etc)
            signal_performance: Historical performance for this signal type
            current_drawdown_pct: Current drawdown as % (0-100)

        Returns:
            AdaptivePositionSize with calculated value and multipliers
        """

        # 1. BASE POSITION: Risk-based sizing
        base_position_pct = params.base_risk_pct
        base_position_usd = (params.account_size * base_position_pct) / 100

        # 2. CONFIDENCE MULTIPLIER (0.5x - 1.5x)
        confidence_mult = AdaptivePositionSizer._interpolate_multiplier(
            params.confidence_score,
            AdaptivePositionSizer.CONFIDENCE_MULTIPLIER_MAP,
        )

        # 3. WIN RATE MULTIPLIER (0.3x - 1.8x)
        win_rate_mult = 1.0  # Default: neutral
        if signal_performance and signal_performance.sample_size_adequate:
            win_rate_mult = AdaptivePositionSizer._interpolate_multiplier(
                signal_performance.win_rate,
                AdaptivePositionSizer.WIN_RATE_MULTIPLIER_MAP,
            )

        # 4. VOLATILITY MULTIPLIER (0.5x - 1.5x)
        volatility_mult = AdaptivePositionSizer._interpolate_multiplier(
            params.atr_ratio,
            AdaptivePositionSizer.VOLATILITY_MULTIPLIER_MAP,
        )

        # 5. STREAK MULTIPLIER (0.7x - 1.2x)
        streak_mult = 1.0
        if signal_performance:
            if signal_performance.consecutive_wins >= 2:
                streak_mult = 1.0 + (
                    min(signal_performance.consecutive_wins - 2, 3) * 0.05
                )
            elif signal_performance.consecutive_losses >= 2:
                streak_mult = max(0.7, 1.0 - (signal_performance.consecutive_losses * 0.15))

        # 6. DRAWDOWN PENALTY (0.5x - 1.0x)
        drawdown_mult = 1.0
        if current_drawdown_pct > 15:
            # Linear reduction: 15% drawdown → 0.7x, 30% → 0.3x
            drawdown_mult = max(0.3, 1.0 - (current_drawdown_pct - 15) / 50)

        # Calculate final position
        raw_multiplier = (
            confidence_mult
            * win_rate_mult
            * volatility_mult
            * streak_mult
            * drawdown_mult
        )
        final_position_usd = base_position_usd * raw_multiplier

        # Apply constraints
        min_position_usd = (params.account_size * AdaptivePositionSizer.MIN_POSITION_PCT) / 100
        max_position_usd = (params.account_size * AdaptivePositionSizer.MAX_POSITION_PCT) / 100

        final_position_usd = max(
            min_position_usd,
            min(max_position_usd, final_position_usd),
        )

        final_position_pct = (final_position_usd / params.account_size) * 100

        # Calculate quantity
        quantity = final_position_usd / params.entry_price if params.entry_price > 0 else 0

        # Reasoning breakdown
        reasoning = {
            "base_position": f"${base_position_usd:.2f} ({params.base_risk_pct}% of account)",
            "confidence_factor": f"{params.signal_rating} score ({params.confidence_score:.0f}) → {confidence_mult:.2f}x",
            "win_rate_factor": (
                f"{signal_performance.win_rate*100:.0f}% win rate "
                f"({signal_performance.winning_trades}/{signal_performance.total_trades} trades) "
                f"→ {win_rate_mult:.2f}x"
                if signal_performance
                else "No historical data → 1.0x (neutral)"
            ),
            "volatility_factor": f"ATR ratio {params.atr_ratio:.2f} → {volatility_mult:.2f}x",
            "streak_factor": (
                f"+{signal_performance.consecutive_wins} wins → {streak_mult:.2f}x"
                if signal_performance and signal_performance.consecutive_wins > 0
                else (
                    f"{signal_performance.consecutive_losses} losses → {streak_mult:.2f}x"
                    if signal_performance and signal_performance.consecutive_losses > 0
                    else "Neutral streak → 1.0x"
                )
            ),
            "drawdown_penalty": (
                f"Current drawdown {current_drawdown_pct:.1f}% → {drawdown_mult:.2f}x"
                if current_drawdown_pct > 0
                else "No drawdown → 1.0x"
            ),
            "final_size": f"${final_position_usd:.2f} ({final_position_pct:.2f}% of account)",
        }

        return AdaptivePositionSize(
            position_value_usd=final_position_usd,
            position_value_pct=final_position_pct,
            quantity=quantity,
            entry_price=params.entry_price,
            confidence_multiplier=confidence_mult,
            win_rate_multiplier=win_rate_mult,
            volatility_multiplier=volatility_mult,
            streak_multiplier=streak_mult,
            reasoning=reasoning,
        )

    @staticmethod
    def _interpolate_multiplier(
        value: float, multiplier_map: Dict[float, float]
    ) -> float:
        """
        Interpolate multiplier for a value using a map.

        Args:
            value: Current value
            multiplier_map: Mapping of value thresholds to multipliers (sorted keys)

        Returns:
            Interpolated multiplier
        """
        sorted_keys = sorted(multiplier_map.keys())

        # Value below minimum threshold
        if value <= sorted_keys[0]:
            return multiplier_map[sorted_keys[0]]

        # Value above maximum threshold
        if value >= sorted_keys[-1]:
            return multiplier_map[sorted_keys[-1]]

        # Interpolate between two thresholds
        for i in range(len(sorted_keys) - 1):
            lower_key = sorted_keys[i]
            upper_key = sorted_keys[i + 1]

            if lower_key <= value <= upper_key:
                lower_mult = multiplier_map[lower_key]
                upper_mult = multiplier_map[upper_key]

                # Linear interpolation
                progress = (value - lower_key) / (upper_key - lower_key)
                return lower_mult + (upper_mult - lower_mult) * progress

        return 1.0  # Default fallback
