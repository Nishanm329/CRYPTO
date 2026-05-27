"""
Performance Analytics Engine

Analyzes trading performance with statistical rigor:
- Win rate, profit factor, payoff ratio
- Sharpe ratio, Sortino ratio, Calmar ratio
- Maximum drawdown, recovery factor
- Trade duration and volatility metrics
- Risk/return analysis
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from statistics import mean, stdev, median
from enum import Enum
from math import sqrt
from logging_config import get_logger
from db import SessionLocal
from models import TradeDB, TradeStatus
from repositories import TradeRepository

logger = get_logger(__name__)

# Risk-free rate (annual) - used for Sharpe/Sortino calculations
RISK_FREE_RATE = 0.02


class MetricType(str, Enum):
    """Performance metric types."""
    WIN_RATE = "WIN_RATE"
    PROFIT_FACTOR = "PROFIT_FACTOR"
    PAYOFF_RATIO = "PAYOFF_RATIO"
    SHARPE_RATIO = "SHARPE_RATIO"
    SORTINO_RATIO = "SORTINO_RATIO"
    CALMAR_RATIO = "CALMAR_RATIO"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    RECOVERY_FACTOR = "RECOVERY_FACTOR"
    TOTAL_RETURN = "TOTAL_RETURN"


class TradeAnalyzer:
    """Analyzes individual trades."""

    @staticmethod
    def calculate_trade_metrics(trade: TradeDB) -> Dict[str, Any]:
        """
        Calculate metrics for a single trade.

        Args:
            trade: TradeDB instance (must be closed)

        Returns:
            Dict with trade metrics
        """
        if not trade.realized_pnl or not trade.realized_pnl_pct:
            return {
                "trade_id": trade.id,
                "status": trade.status,
                "error": "Trade not fully closed (missing P&L)",
            }

        # Calculate duration
        duration_hours = (trade.exit_timestamp - trade.entry_timestamp).total_seconds() / 3600 if trade.exit_timestamp else 0

        # Risk/Reward calculation
        if trade.stop_loss and trade.take_profit_1:
            if trade.direction == "LONG":
                risk = trade.entry_price - trade.stop_loss
                reward = trade.take_profit_1 - trade.entry_price
            else:  # SHORT
                risk = trade.stop_loss - trade.entry_price
                reward = trade.entry_price - trade.take_profit_1

            rr_ratio = reward / risk if risk > 0 else 0
        else:
            rr_ratio = None

        return {
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "quantity": trade.quantity,
            "entry_value": trade.entry_value,
            "exit_value": (trade.exit_price * trade.exit_quantity) if (trade.exit_price and trade.exit_quantity) else 0,
            "realized_pnl": trade.realized_pnl,
            "realized_pnl_pct": trade.realized_pnl_pct,
            "duration_hours": duration_hours,
            "duration_days": duration_hours / 24,
            "entry_date": trade.entry_timestamp.isoformat() if trade.entry_timestamp else None,
            "exit_date": trade.exit_timestamp.isoformat() if trade.exit_timestamp else None,
            "exit_reason": trade.exit_reason,
            "is_profitable": trade.realized_pnl > 0,
            "rr_ratio": rr_ratio,
            "fees": trade.fees or 0,
        }

    @staticmethod
    def is_profitable(trade: TradeDB) -> bool:
        """Check if trade is profitable."""
        return trade.realized_pnl is not None and trade.realized_pnl > 0


class PortfolioAnalyzer:
    """Analyzes complete trading performance."""

    @staticmethod
    def calculate_win_metrics(trades: List[TradeDB]) -> Dict[str, float]:
        """
        Calculate win/loss metrics.

        Args:
            trades: List of closed trades

        Returns:
            Dict with win rate, win/loss counts, etc.
        """
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "push_trades": 0,
            }

        profitable = [t for t in trades if t.realized_pnl and t.realized_pnl > 0.001]
        losing = [t for t in trades if t.realized_pnl and t.realized_pnl < -0.001]
        push = [t for t in trades if t.realized_pnl and abs(t.realized_pnl) <= 0.001]

        win_rate = (len(profitable) / len(trades) * 100) if trades else 0

        return {
            "total_trades": len(trades),
            "winning_trades": len(profitable),
            "losing_trades": len(losing),
            "push_trades": len(push),
            "win_rate": round(win_rate, 2),
            "loss_rate": round(100 - win_rate, 2),
        }

    @staticmethod
    def calculate_profit_metrics(trades: List[TradeDB]) -> Dict[str, float]:
        """
        Calculate profit-based metrics.

        Args:
            trades: List of closed trades

        Returns:
            Dict with gross profit, profit factor, payoff ratio, etc.
        """
        if not trades or not any(t.realized_pnl for t in trades):
            return {
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "total_pnl": 0.0,
                "profit_factor": 0.0,
                "payoff_ratio": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
            }

        profitable = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
        losing = [t for t in trades if t.realized_pnl and t.realized_pnl < 0]

        gross_profit = sum(t.realized_pnl for t in profitable)
        gross_loss = sum(abs(t.realized_pnl) for t in losing)
        total_pnl = gross_profit - gross_loss

        # Profit factor = gross_profit / gross_loss
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (
            gross_profit if gross_profit > 0 else 0
        )

        # Payoff ratio = avg_win / avg_loss
        avg_win = mean([t.realized_pnl for t in profitable]) if profitable else 0
        avg_loss = mean([abs(t.realized_pnl) for t in losing]) if losing else 0
        payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        return {
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "total_pnl": round(total_pnl, 2),
            "profit_factor": round(profit_factor, 2),
            "payoff_ratio": round(payoff_ratio, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
        }

    @staticmethod
    def calculate_return_metrics(
        trades: List[TradeDB],
        initial_capital: float,
    ) -> Dict[str, float]:
        """
        Calculate return-based metrics.

        Args:
            trades: List of closed trades
            initial_capital: Starting capital

        Returns:
            Dict with ROI, CAGR, return %, etc.
        """
        if not trades or initial_capital <= 0:
            return {
                "total_return": 0.0,
                "return_pct": 0.0,
                "avg_return_per_trade": 0.0,
                "return_per_unit_risk": 0.0,
            }

        total_pnl = sum(t.realized_pnl or 0 for t in trades)
        return_pct = (total_pnl / initial_capital) * 100

        avg_return = (total_pnl / len(trades)) if trades else 0
        avg_return_pct = (avg_return / initial_capital) * 100

        # Return per unit of risk (capital at risk)
        total_risk = sum(abs(t.realized_pnl) for t in trades if t.realized_pnl and t.realized_pnl < 0)
        return_per_unit_risk = total_pnl / total_risk if total_risk > 0 else 0

        return {
            "total_return": round(total_pnl, 2),
            "return_pct": round(return_pct, 2),
            "avg_return_per_trade": round(avg_return, 2),
            "avg_return_per_trade_pct": round(avg_return_pct, 2),
            "return_per_unit_risk": round(return_per_unit_risk, 2),
        }

    @staticmethod
    def calculate_duration_metrics(trades: List[TradeDB]) -> Dict[str, float]:
        """
        Calculate trade duration metrics.

        Args:
            trades: List of closed trades

        Returns:
            Dict with average duration, median, min/max
        """
        if not trades:
            return {
                "avg_duration_hours": 0.0,
                "avg_duration_days": 0.0,
                "median_duration_hours": 0.0,
                "min_duration_hours": 0.0,
                "max_duration_hours": 0.0,
            }

        durations = []
        for trade in trades:
            if trade.entry_timestamp and trade.exit_timestamp:
                duration = (trade.exit_timestamp - trade.entry_timestamp).total_seconds() / 3600
                durations.append(duration)

        if not durations:
            return {
                "avg_duration_hours": 0.0,
                "avg_duration_days": 0.0,
                "median_duration_hours": 0.0,
                "min_duration_hours": 0.0,
                "max_duration_hours": 0.0,
            }

        return {
            "avg_duration_hours": round(mean(durations), 2),
            "avg_duration_days": round(mean(durations) / 24, 2),
            "median_duration_hours": round(median(durations), 2),
            "min_duration_hours": round(min(durations), 2),
            "max_duration_hours": round(max(durations), 2),
        }

    @staticmethod
    def calculate_best_worst_trades(trades: List[TradeDB]) -> Dict[str, Any]:
        """
        Find best and worst trades.

        Args:
            trades: List of closed trades

        Returns:
            Dict with best/worst trade details
        """
        if not trades:
            return {
                "best_trade": None,
                "worst_trade": None,
            }

        valid_trades = [t for t in trades if t.realized_pnl is not None]
        if not valid_trades:
            return {
                "best_trade": None,
                "worst_trade": None,
            }

        best = max(valid_trades, key=lambda t: t.realized_pnl)
        worst = min(valid_trades, key=lambda t: t.realized_pnl)

        return {
            "best_trade": {
                "id": best.id,
                "symbol": best.symbol,
                "pnl": round(best.realized_pnl, 2),
                "pnl_pct": round(best.realized_pnl_pct or 0, 2),
            },
            "worst_trade": {
                "id": worst.id,
                "symbol": worst.symbol,
                "pnl": round(worst.realized_pnl, 2),
                "pnl_pct": round(worst.realized_pnl_pct or 0, 2),
            },
        }


class DrawdownAnalyzer:
    """Analyzes drawdown and equity curve."""

    @staticmethod
    def calculate_drawdown(
        trades: List[TradeDB],
        initial_capital: float,
    ) -> Dict[str, Any]:
        """
        Calculate maximum drawdown.

        Args:
            trades: List of trades (sorted by exit timestamp)
            initial_capital: Starting capital

        Returns:
            Dict with max drawdown, duration, etc.
        """
        if not trades or initial_capital <= 0:
            return {
                "max_drawdown_pct": 0.0,
                "max_drawdown_usd": 0.0,
                "drawdown_duration_days": 0,
                "current_drawdown_pct": 0.0,
            }

        # Build equity curve
        equity = initial_capital
        peak = initial_capital
        max_dd = 0
        max_dd_pct = 0
        dd_start = None
        dd_end = None
        max_dd_duration = 0

        for trade in trades:
            equity += trade.realized_pnl or 0

            # Calculate drawdown from peak
            if equity < peak:
                dd = peak - equity
                dd_pct = (dd / peak) * 100

                if dd > max_dd:
                    max_dd = dd
                    max_dd_pct = dd_pct
                    dd_start = trade.entry_timestamp
                    dd_end = trade.exit_timestamp

            # Update peak
            if equity > peak:
                if dd_start and dd_end:
                    duration = (dd_end - dd_start).days
                    if duration > max_dd_duration:
                        max_dd_duration = duration

                peak = equity

        return {
            "max_drawdown_pct": round(max_dd_pct, 2),
            "max_drawdown_usd": round(max_dd, 2),
            "drawdown_duration_days": max_dd_duration,
            "current_drawdown_pct": round(((peak - equity) / peak) * 100, 2) if peak > 0 else 0,
        }

    @staticmethod
    def calculate_recovery_factor(
        trades: List[TradeDB],
        initial_capital: float,
    ) -> float:
        """
        Calculate recovery factor = total_profit / max_drawdown.

        Args:
            trades: List of closed trades
            initial_capital: Starting capital

        Returns:
            Recovery factor
        """
        total_profit = sum(t.realized_pnl or 0 for t in trades)
        drawdown_data = DrawdownAnalyzer.calculate_drawdown(trades, initial_capital)
        max_dd = drawdown_data["max_drawdown_usd"]

        if max_dd <= 0:
            return 0.0

        return round(total_profit / max_dd, 2)


class StatisticalAnalyzer:
    """Calculates statistical performance metrics."""

    @staticmethod
    def calculate_sharpe_ratio(
        trades: List[TradeDB],
        initial_capital: float,
        periods_per_year: int = 252,
    ) -> float:
        """
        Calculate Sharpe ratio (return per unit of volatility).

        Args:
            trades: List of closed trades
            initial_capital: Starting capital
            periods_per_year: Trading periods per year (252 for daily)

        Returns:
            Sharpe ratio
        """
        if not trades or initial_capital <= 0:
            return 0.0

        # Calculate returns
        returns = [(t.realized_pnl or 0) / initial_capital for t in trades]

        if len(returns) < 2:
            return 0.0

        avg_return = mean(returns)
        volatility = stdev(returns) if len(returns) > 1 else 0

        if volatility == 0:
            return 0.0

        # Sharpe = (avg_return - risk_free_rate) / volatility * sqrt(periods_per_year)
        annualized_sharpe = ((avg_return - RISK_FREE_RATE / 252) / volatility) * sqrt(periods_per_year)

        return round(annualized_sharpe, 2)

    @staticmethod
    def calculate_sortino_ratio(
        trades: List[TradeDB],
        initial_capital: float,
        periods_per_year: int = 252,
    ) -> float:
        """
        Calculate Sortino ratio (return per unit of downside volatility).

        Args:
            trades: List of closed trades
            initial_capital: Starting capital
            periods_per_year: Trading periods per year

        Returns:
            Sortino ratio
        """
        if not trades or initial_capital <= 0:
            return 0.0

        returns = [(t.realized_pnl or 0) / initial_capital for t in trades]

        if len(returns) < 2:
            return 0.0

        avg_return = mean(returns)

        # Calculate downside volatility (only negative returns)
        downside_returns = [r for r in returns if r < 0]

        if not downside_returns:
            downside_vol = 0
        else:
            downside_vol = stdev(downside_returns) if len(downside_returns) > 1 else 0

        if downside_vol == 0:
            return 0.0

        # Sortino = (avg_return - risk_free_rate) / downside_volatility * sqrt(periods_per_year)
        annualized_sortino = ((avg_return - RISK_FREE_RATE / 252) / downside_vol) * sqrt(periods_per_year)

        return round(annualized_sortino, 2)

    @staticmethod
    def calculate_calmar_ratio(
        trades: List[TradeDB],
        initial_capital: float,
    ) -> float:
        """
        Calculate Calmar ratio = annual_return / max_drawdown.

        Args:
            trades: List of closed trades
            initial_capital: Starting capital

        Returns:
            Calmar ratio
        """
        total_return = sum(t.realized_pnl or 0 for t in trades)
        drawdown_data = DrawdownAnalyzer.calculate_drawdown(trades, initial_capital)
        max_dd_pct = drawdown_data["max_drawdown_pct"]

        if max_dd_pct == 0:
            return 0.0

        annual_return = (total_return / initial_capital) * 100

        return round(annual_return / max_dd_pct, 2)


class PerformanceReportGenerator:
    """Generates comprehensive performance reports."""

    @staticmethod
    async def generate_report(
        db: SessionLocal,
        user_id: str,
        initial_capital: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate complete performance report.

        Args:
            db: Database session
            user_id: User ID
            initial_capital: Starting capital
            start_date: Filter trades after this date
            end_date: Filter trades before this date

        Returns:
            Comprehensive performance report
        """
        try:
            # Get closed trades
            trades = TradeRepository.get_user_trades(db, user_id)
            trades = [t for t in trades if t.status == TradeStatus.CLOSED.value]

            # Filter by date range
            if start_date:
                trades = [t for t in trades if t.exit_timestamp and t.exit_timestamp >= start_date]
            if end_date:
                trades = [t for t in trades if t.exit_timestamp and t.exit_timestamp <= end_date]

            # Sort by exit date
            trades = sorted(trades, key=lambda t: t.exit_timestamp or datetime.min)

            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "capital": {
                    "initial": initial_capital,
                },
                "summary": {
                    "total_trades": len(trades),
                },
            }

            # Calculate all metrics
            report["wins_losses"] = PortfolioAnalyzer.calculate_win_metrics(trades)
            report["profits"] = PortfolioAnalyzer.calculate_profit_metrics(trades)
            report["returns"] = PortfolioAnalyzer.calculate_return_metrics(trades, initial_capital)
            report["duration"] = PortfolioAnalyzer.calculate_duration_metrics(trades)
            report["best_worst"] = PortfolioAnalyzer.calculate_best_worst_trades(trades)
            report["drawdown"] = DrawdownAnalyzer.calculate_drawdown(trades, initial_capital)
            report["recovery_factor"] = DrawdownAnalyzer.calculate_recovery_factor(trades, initial_capital)

            # Statistical ratios
            report["statistics"] = {
                "sharpe_ratio": StatisticalAnalyzer.calculate_sharpe_ratio(trades, initial_capital),
                "sortino_ratio": StatisticalAnalyzer.calculate_sortino_ratio(trades, initial_capital),
                "calmar_ratio": StatisticalAnalyzer.calculate_calmar_ratio(trades, initial_capital),
            }

            logger.info(
                f"Performance report generated for {user_id}",
                action="report_generated",
                user_id=user_id,
                total_trades=len(trades),
                total_return=report["returns"].get("total_return"),
                win_rate=report["wins_losses"].get("win_rate"),
            )

            return report

        except Exception as e:
            logger.error(
                f"Failed to generate performance report for {user_id}",
                action="report_generation_failed",
                user_id=user_id,
                error=str(e),
            )
            raise
