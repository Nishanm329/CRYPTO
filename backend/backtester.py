"""
Backtesting engine.
Replays EMA cross signals on historical OHLCV data and computes
performance metrics: win rate, profit factor, max drawdown, Sharpe ratio.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datetime import datetime, timedelta

from binance_client import get_klines
from indicators import add_all_indicators, detect_ema_cross
from models import BacktestResult


def _simulate_trade(
    df: pd.DataFrame,
    entry_idx: int,
    direction: str,
    atr_mult_sl: float = 2.0,
    atr_mult_tp: float = 3.0,
) -> Dict[str, Any]:
    """
    Simulate a single trade starting at entry_idx.
    Returns a trade result dict.
    """
    entry_bar = df.iloc[entry_idx]
    entry_price = entry_bar["close"]
    atr = entry_bar["atr"]

    if direction == "LONG":
        sl = entry_price - atr_mult_sl * atr
        tp = entry_price + atr_mult_tp * atr
    else:
        sl = entry_price + atr_mult_sl * atr
        tp = entry_price - atr_mult_tp * atr

    # Walk forward through subsequent candles
    for i in range(entry_idx + 1, min(entry_idx + 100, len(df))):
        bar = df.iloc[i]

        if direction == "LONG":
            if bar["low"] <= sl:
                return {
                    "outcome": "LOSS",
                    "entry": entry_price,
                    "exit": sl,
                    "pnl_pct": (sl - entry_price) / entry_price * 100,
                    "bars_held": i - entry_idx,
                    "direction": direction,
                    "entry_time": str(df["timestamp"].iloc[entry_idx]),
                    "exit_time": str(df["timestamp"].iloc[i]),
                }
            if bar["high"] >= tp:
                return {
                    "outcome": "WIN",
                    "entry": entry_price,
                    "exit": tp,
                    "pnl_pct": (tp - entry_price) / entry_price * 100,
                    "bars_held": i - entry_idx,
                    "direction": direction,
                    "entry_time": str(df["timestamp"].iloc[entry_idx]),
                    "exit_time": str(df["timestamp"].iloc[i]),
                }
        else:
            if bar["high"] >= sl:
                return {
                    "outcome": "LOSS",
                    "entry": entry_price,
                    "exit": sl,
                    "pnl_pct": (entry_price - sl) / entry_price * 100,
                    "bars_held": i - entry_idx,
                    "direction": direction,
                    "entry_time": str(df["timestamp"].iloc[entry_idx]),
                    "exit_time": str(df["timestamp"].iloc[i]),
                }
            if bar["low"] <= tp:
                return {
                    "outcome": "WIN",
                    "entry": entry_price,
                    "exit": tp,
                    "pnl_pct": (entry_price - tp) / entry_price * 100,
                    "bars_held": i - entry_idx,
                    "direction": direction,
                    "entry_time": str(df["timestamp"].iloc[entry_idx]),
                    "exit_time": str(df["timestamp"].iloc[i]),
                }

    # Timeout: close at current price
    exit_price = df.iloc[min(entry_idx + 99, len(df) - 1)]["close"]
    pnl = (exit_price - entry_price) / entry_price * 100
    if direction == "SHORT":
        pnl = -pnl

    return {
        "outcome": "WIN" if pnl > 0 else "LOSS",
        "entry": entry_price,
        "exit": exit_price,
        "pnl_pct": pnl,
        "bars_held": min(99, len(df) - 1 - entry_idx),
        "direction": direction,
        "entry_time": str(df["timestamp"].iloc[entry_idx]),
        "exit_time": str(df["timestamp"].iloc[min(entry_idx + 99, len(df) - 1)]),
    }


def _calc_sharpe(returns: List[float], risk_free: float = 0.0) -> float:
    if not returns or len(returns) < 2:
        return 0.0
    arr = np.array(returns)
    excess = arr - risk_free
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(252))


def _calc_max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0.0
    arr = np.array(equity_curve)
    peak = arr[0]
    max_dd = 0.0
    for v in arr:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


async def run_backtest(
    symbol: str,
    timeframe: str,
    atr_mult_sl: float = 2.0,
    atr_mult_tp: float = 3.0,
    limit: int = 500,
) -> BacktestResult:
    """
    Run a full backtest for EMA 7/25 cross strategy on historical data.
    """
    df = await get_klines(symbol, timeframe, limit=limit)
    df = add_all_indicators(df)

    # Drop NaN rows (initial indicator warm-up period)
    df = df.dropna(subset=["ema7", "ema25", "rsi", "atr"]).reset_index()

    trades = []
    last_cross_idx = -10  # prevent double-counting
    next_entry_after = 0  # no new trade until this index (prevents overlaps)

    for i in range(2, len(df) - 1):
        # Skip if still inside a previous trade's bars_held window
        if i < next_entry_after:
            continue

        prev_above = df["ema7"].iloc[i - 1] > df["ema25"].iloc[i - 1]
        curr_above = df["ema7"].iloc[i] > df["ema25"].iloc[i]

        if not prev_above and curr_above and i - last_cross_idx > 3:
            direction = "LONG"
        elif prev_above and not curr_above and i - last_cross_idx > 3:
            direction = "SHORT"
        else:
            continue

        last_cross_idx = i
        trade = _simulate_trade(df, i, direction, atr_mult_sl, atr_mult_tp)
        trades.append(trade)
        # Block new entries until this trade closes
        next_entry_after = i + trade["bars_held"] + 1

    if not trades:
        return BacktestResult(
            strategy="EMA 7/25 Cross",
            symbol=symbol,
            timeframe=timeframe,
            start_date=str(df["timestamp"].iloc[0]) if "timestamp" in df.columns else "",
            end_date=str(df["timestamp"].iloc[-1]) if "timestamp" in df.columns else "",
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            avg_trade_duration_hours=0.0,
            total_return_pct=0.0,
            best_trade_pct=0.0,
            worst_trade_pct=0.0,
            trades=[],
        )

    wins = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]

    win_rate = len(wins) / len(trades) * 100

    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) or 0.001
    profit_factor = round(gross_profit / gross_loss, 2)

    returns = [t["pnl_pct"] for t in trades]
    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))

    total_return = round(equity[-1] - 100, 2)
    max_dd = _calc_max_drawdown(equity)
    sharpe = round(_calc_sharpe(returns), 2)

    # Average bars held → hours (approximate)
    avg_bars = np.mean([t["bars_held"] for t in trades])
    tf_hours = {
        "1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5,
        "1h": 1, "4h": 4, "1d": 24, "3d": 72, "1w": 168,
    }
    avg_hours = round(avg_bars * tf_hours.get(timeframe, 1), 1)

    best = round(max(returns), 2)
    worst = round(min(returns), 2)

    ts_col = "timestamp" if "timestamp" in df.columns else df.index.name or "index"

    return BacktestResult(
        strategy="EMA 7/25 Cross",
        symbol=symbol,
        timeframe=timeframe,
        start_date=str(df.iloc[0].get("timestamp", "")),
        end_date=str(df.iloc[-1].get("timestamp", "")),
        total_trades=len(trades),
        win_rate=round(win_rate, 1),
        profit_factor=profit_factor,
        max_drawdown=max_dd,
        sharpe_ratio=sharpe,
        avg_trade_duration_hours=avg_hours,
        total_return_pct=total_return,
        best_trade_pct=best,
        worst_trade_pct=worst,
        trades=trades[-50:],  # Return last 50 trades
    )
