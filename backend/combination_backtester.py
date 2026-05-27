"""
Indicator Combination Backtester
=================================
Tests 12 distinct indicator filter combinations layered on top of the
EMA 7/25 crossover base signal across up to 6 years of historical daily
(or 4h) candle data from Binance.

Each combination adds progressive filtering gates to the raw EMA cross
signal, requiring additional indicators to confirm before a trade entry
is allowed.  Results are ranked by Sharpe ratio (primary) then by
profit factor (secondary) to surface the best risk-adjusted strategies.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

import numpy as np
import pandas as pd

from binance_client import get_historical_klines
from indicators import add_all_indicators, calculate_stoch_rsi


# ── Combination Catalogue ────────────────────────────────────────────────────

COMBINATIONS: List[Dict[str, Any]] = [
    {
        "id": "ema_only",
        "name": "EMA Cross Only",
        "description": "Pure EMA 7/25 crossover — no additional filters",
        "filters": set(),
    },
    {
        "id": "ema_rsi",
        "name": "EMA + RSI",
        "description": "EMA cross confirmed by RSI outside extreme zones (30–70)",
        "filters": {"rsi"},
    },
    {
        "id": "ema_macd",
        "name": "EMA + MACD",
        "description": "EMA cross confirmed by MACD histogram momentum direction",
        "filters": {"macd"},
    },
    {
        "id": "ema_bb",
        "name": "EMA + Bollinger",
        "description": "EMA cross with price not at extremes of Bollinger Bands",
        "filters": {"bb"},
    },
    {
        "id": "ema_vol",
        "name": "EMA + Volume",
        "description": "EMA cross on above-average volume (vol_ratio > 1.1×)",
        "filters": {"volume"},
    },
    {
        "id": "ema_stochrsi",
        "name": "EMA + StochRSI",
        "description": "EMA cross confirmed by StochRSI not at extreme level",
        "filters": {"stochrsi"},
    },
    {
        "id": "ema_rsi_macd",
        "name": "EMA + RSI + MACD",
        "description": "Triple confluence: EMA cross + RSI zone + MACD momentum",
        "filters": {"rsi", "macd"},
    },
    {
        "id": "ema_rsi_vol",
        "name": "EMA + RSI + Volume",
        "description": "EMA cross + RSI zone filter + volume confirmation",
        "filters": {"rsi", "volume"},
    },
    {
        "id": "ema_macd_bb",
        "name": "EMA + MACD + BB",
        "description": "EMA cross + MACD momentum + Bollinger Band positioning",
        "filters": {"macd", "bb"},
    },
    {
        "id": "ema_rsi_macd_vol",
        "name": "EMA + RSI + MACD + Volume",
        "description": "Four-factor confluence: EMA + RSI + MACD + volume spike",
        "filters": {"rsi", "macd", "volume"},
    },
    {
        "id": "ema_rsi_macd_bb",
        "name": "EMA + RSI + MACD + BB",
        "description": "Four-indicator technical confluence with BB positioning",
        "filters": {"rsi", "macd", "bb"},
    },
    {
        "id": "full_confluence",
        "name": "Full Confluence",
        "description": "All six indicators must align: EMA + RSI + MACD + BB + Volume + StochRSI",
        "filters": {"rsi", "macd", "bb", "volume", "stochrsi"},
    },
]


# ── Filter Gate Logic ─────────────────────────────────────────────────────────

def _passes_filters(row: pd.Series, direction: str, filters: Set[str]) -> bool:
    """
    Return True if the entry bar satisfies every required indicator filter.
    A single failing condition vetoes the entire entry.
    """
    for f in filters:
        if f == "rsi":
            rsi = row.get("rsi")
            if pd.isna(rsi):
                return False
            if direction == "LONG" and rsi >= 70:   # do not buy overbought
                return False
            if direction == "SHORT" and rsi <= 30:  # do not short oversold
                return False

        elif f == "macd":
            hist = row.get("macd_hist")
            if pd.isna(hist):
                return False
            if direction == "LONG" and hist <= 0:   # need bullish MACD momentum
                return False
            if direction == "SHORT" and hist >= 0:  # need bearish MACD momentum
                return False

        elif f == "bb":
            bb_pct = row.get("bb_pct")  # (close - lower) / (upper - lower), 0-1
            if pd.isna(bb_pct):
                return False
            # Avoid longs near the very top of the band
            if direction == "LONG" and bb_pct > 0.85:
                return False
            # Avoid shorts near the very bottom of the band
            if direction == "SHORT" and bb_pct < 0.15:
                return False

        elif f == "volume":
            vol_ratio = row.get("vol_ratio")
            if pd.isna(vol_ratio):
                return False
            if vol_ratio < 1.1:  # require above-average volume
                return False

        elif f == "stochrsi":
            stoch_k = row.get("stoch_k")
            if pd.isna(stoch_k):
                return False
            if direction == "LONG" and stoch_k >= 80:   # overbought
                return False
            if direction == "SHORT" and stoch_k <= 20:  # oversold
                return False

    return True


# ── Single-Trade Simulation ───────────────────────────────────────────────────

def _simulate_trade(
    df: pd.DataFrame,
    entry_idx: int,
    direction: str,
    atr_mult_sl: float = 2.0,
    atr_mult_tp: float = 3.0,
) -> Dict[str, Any]:
    """
    Walk forward from entry_idx, checking SL/TP hits bar by bar.
    Returns a minimal trade dict: outcome, pnl_pct, bars_held.
    """
    entry_price = float(df["close"].iloc[entry_idx])
    atr = float(df["atr"].iloc[entry_idx])

    if direction == "LONG":
        sl = entry_price - atr_mult_sl * atr
        tp = entry_price + atr_mult_tp * atr
    else:
        sl = entry_price + atr_mult_sl * atr
        tp = entry_price - atr_mult_tp * atr

    max_bar = min(entry_idx + 100, len(df))
    for i in range(entry_idx + 1, max_bar):
        low = float(df["low"].iloc[i])
        high = float(df["high"].iloc[i])

        if direction == "LONG":
            if low <= sl:
                return {
                    "outcome": "LOSS",
                    "pnl_pct": (sl - entry_price) / entry_price * 100,
                    "bars_held": i - entry_idx,
                }
            if high >= tp:
                return {
                    "outcome": "WIN",
                    "pnl_pct": (tp - entry_price) / entry_price * 100,
                    "bars_held": i - entry_idx,
                }
        else:
            if high >= sl:
                return {
                    "outcome": "LOSS",
                    "pnl_pct": (entry_price - sl) / entry_price * 100,
                    "bars_held": i - entry_idx,
                }
            if low <= tp:
                return {
                    "outcome": "WIN",
                    "pnl_pct": (entry_price - tp) / entry_price * 100,
                    "bars_held": i - entry_idx,
                }

    # Timeout — exit at last available bar
    exit_price = float(df["close"].iloc[min(entry_idx + 99, len(df) - 1)])
    pnl = (exit_price - entry_price) / entry_price * 100
    if direction == "SHORT":
        pnl = -pnl
    return {
        "outcome": "WIN" if pnl > 0 else "LOSS",
        "pnl_pct": pnl,
        "bars_held": min(99, len(df) - 1 - entry_idx),
    }


# ── Performance Metrics ───────────────────────────────────────────────────────

def _compute_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute full performance statistics from a list of trade dicts."""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "total_return_pct": 0.0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "avg_bars": 0.0,
            "equity_curve": [100.0],
        }

    wins = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]
    returns = [t["pnl_pct"] for t in trades]

    win_rate = len(wins) / len(trades) * 100
    gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0.0
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0.001
    profit_factor = round(gross_profit / gross_loss, 2)

    # Build equity curve (compounded, starting at 100)
    equity: List[float] = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))

    # Max drawdown
    arr = np.array(equity)
    peak = arr[0]
    max_dd = 0.0
    for v in arr:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Annualised Sharpe (using per-trade returns, √252 scaling for daily equiv)
    ret_arr = np.array(returns)
    sharpe = 0.0
    if len(ret_arr) >= 2 and ret_arr.std() > 0:
        sharpe = float(ret_arr.mean() / ret_arr.std() * np.sqrt(252))

    # Downsample equity to ≤60 points for the sparkline
    step = max(1, len(equity) // 60)
    equity_ds = [round(v, 2) for v in equity[::step]]
    if equity_ds[-1] != round(equity[-1], 2):
        equity_ds.append(round(equity[-1], 2))

    return {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 1),
        "profit_factor": profit_factor,
        "max_drawdown": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 2),
        "total_return_pct": round(equity[-1] - 100, 2),
        "best_trade_pct": round(max(returns), 2),
        "worst_trade_pct": round(min(returns), 2),
        "avg_bars": round(float(np.mean([t["bars_held"] for t in trades])), 1),
        "equity_curve": equity_ds,
    }


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def run_combination_backtest(
    symbol: str,
    timeframe: str = "1d",
    years: int = 6,
    atr_mult_sl: float = 2.0,
    atr_mult_tp: float = 3.0,
) -> Dict[str, Any]:
    """
    Fetch up to `years` of historical OHLCV data, add all indicators,
    then simulate every combination and return a ranked leaderboard.
    """
    start_ms = int(
        (datetime.utcnow() - timedelta(days=years * 365)).timestamp() * 1000
    )

    # --- Data fetch (paginated) ---
    df = await get_historical_klines(symbol, timeframe, start_ms)
    df = add_all_indicators(df)

    stoch_k, stoch_d = calculate_stoch_rsi(df["rsi"])
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d

    required = ["ema7", "ema25", "rsi", "atr", "macd_hist", "bb_pct", "vol_ratio", "stoch_k"]
    df = df.dropna(subset=required).reset_index()

    if len(df) < 50:
        raise ValueError(
            f"Not enough data for {symbol} {timeframe} ({len(df)} bars after warm-up)"
        )

    start_date = str(df["timestamp"].iloc[0])
    end_date = str(df["timestamp"].iloc[-1])
    total_bars = len(df)

    # --- Simulate each combination ---
    results: List[Dict[str, Any]] = []

    for combo in COMBINATIONS:
        filters: Set[str] = combo["filters"]
        trades: List[Dict[str, Any]] = []
        last_cross_idx = -10
        next_entry_after = 0

        for i in range(2, len(df) - 1):
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

            # Additional indicator gate
            if not _passes_filters(df.iloc[i], direction, filters):
                continue

            last_cross_idx = i
            trade = _simulate_trade(df, i, direction, atr_mult_sl, atr_mult_tp)
            trades.append(trade)
            next_entry_after = i + trade["bars_held"] + 1

        metrics = _compute_metrics(trades)
        results.append({
            "id": combo["id"],
            "name": combo["name"],
            "description": combo["description"],
            "filter_count": len(filters),
            "filters": sorted(list(filters)),
            **metrics,
        })

    # --- Rank: Sharpe primary, profit_factor secondary ---
    results.sort(
        key=lambda r: (r["sharpe_ratio"], r["profit_factor"]),
        reverse=True,
    )
    for idx, r in enumerate(results):
        r["rank"] = idx + 1

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "years_tested": years,
        "start_date": start_date,
        "end_date": end_date,
        "total_bars": total_bars,
        "combinations_tested": len(results),
        "results": results,
        "best_combination": results[0]["name"] if results else None,
        "best_sharpe": results[0]["sharpe_ratio"] if results else 0.0,
        "generated_at": datetime.utcnow().isoformat(),
    }
