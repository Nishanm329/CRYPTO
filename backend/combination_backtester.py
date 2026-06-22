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


# ── Reusable trade collection over a bar-index window ─────────────────────────

def _collect_trades(
    df: pd.DataFrame,
    filters: Set[str],
    lo: int,
    hi: int,
    atr_mult_sl: float = 2.0,
    atr_mult_tp: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Run the EMA-cross + filter strategy, taking entries only on bars whose
    index falls in [lo, hi). Trade exits may extend past `hi` (a position is
    held until SL/TP), which is the realistic out-of-sample behavior.
    """
    trades: List[Dict[str, Any]] = []
    last_cross_idx = -10
    next_entry_after = 0
    lo = max(2, lo)
    hi = min(hi, len(df) - 1)

    for i in range(lo, hi):
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
        if not _passes_filters(df.iloc[i], direction, filters):
            continue
        last_cross_idx = i
        trade = _simulate_trade(df, i, direction, atr_mult_sl, atr_mult_tp)
        trades.append(trade)
        next_entry_after = i + trade["bars_held"] + 1

    return trades


async def _prepare_history(symbol: str, timeframe: str, years: int) -> pd.DataFrame:
    """Fetch history, add indicators + StochRSI, drop warm-up NaNs."""
    start_ms = int(
        (datetime.utcnow() - timedelta(days=years * 365)).timestamp() * 1000
    )
    df = await get_historical_klines(symbol, timeframe, start_ms)
    df = add_all_indicators(df)
    stoch_k, stoch_d = calculate_stoch_rsi(df["rsi"])
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d
    required = ["ema7", "ema25", "rsi", "atr", "macd_hist", "bb_pct", "vol_ratio", "stoch_k"]
    return df.dropna(subset=required).reset_index()


# ── Walk-Forward Validation ───────────────────────────────────────────────────

async def run_walk_forward_backtest(
    symbol: str,
    timeframe: str = "1d",
    years: int = 6,
    n_splits: int = 5,
    atr_mult_sl: float = 2.0,
    atr_mult_tp: float = 3.0,
) -> Dict[str, Any]:
    """
    Walk-forward (out-of-sample) validation of the combination strategies.

    The in-sample backtest picks whichever combo looked best on the SAME data
    it's scored on — that overstates real performance (curve-fitting). This
    instead splits history into sequential folds: on each fold it selects the
    best combo using only PAST data (training), then measures that combo on the
    next, unseen window (test). Aggregating the test-window trades gives an
    honest estimate, and the in-sample vs out-of-sample gap reveals overfitting.
    """
    df = await _prepare_history(symbol, timeframe, years)
    if len(df) < (n_splits + 1) * 30:
        raise ValueError(
            f"Not enough data for {symbol} {timeframe} walk-forward "
            f"({len(df)} bars; need ~{(n_splits + 1) * 30})"
        )

    n = len(df)
    fold_size = n // (n_splits + 1)

    folds: List[Dict[str, Any]] = []
    oos_trades: List[Dict[str, Any]] = []

    for k in range(1, n_splits + 1):
        train_hi = fold_size * k          # expanding (anchored) training window
        test_lo, test_hi = fold_size * k, fold_size * (k + 1)

        # Select the best combo using ONLY in-sample (training) bars.
        best_combo = None
        best_train_metrics: Dict[str, Any] = {}
        best_score = (-1e9, -1e9)
        for combo in COMBINATIONS:
            tr = _collect_trades(df, combo["filters"], 2, train_hi, atr_mult_sl, atr_mult_tp)
            m = _compute_metrics(tr)
            score = (m["sharpe_ratio"], m["profit_factor"])
            if m["total_trades"] >= 5 and score > best_score:
                best_score = score
                best_combo = combo
                best_train_metrics = m

        # Fallback if no combo cleared the trade-count floor in training.
        if best_combo is None:
            best_combo = COMBINATIONS[0]
            best_train_metrics = _compute_metrics(
                _collect_trades(df, best_combo["filters"], 2, train_hi, atr_mult_sl, atr_mult_tp)
            )

        # Evaluate the CHOSEN combo on the next, unseen window.
        test_trades = _collect_trades(
            df, best_combo["filters"], test_lo, test_hi, atr_mult_sl, atr_mult_tp
        )
        oos_trades.extend(test_trades)
        test_metrics = _compute_metrics(test_trades)

        folds.append({
            "fold": k,
            "chosen_combo": best_combo["name"],
            "chosen_combo_id": best_combo["id"],
            "train_period": [str(df["timestamp"].iloc[0]), str(df["timestamp"].iloc[train_hi - 1])],
            "test_period": [str(df["timestamp"].iloc[test_lo]), str(df["timestamp"].iloc[min(test_hi, n) - 1])],
            "in_sample_sharpe": best_train_metrics.get("sharpe_ratio", 0.0),
            "in_sample_win_rate": best_train_metrics.get("win_rate", 0.0),
            "out_sample_sharpe": test_metrics["sharpe_ratio"],
            "out_sample_win_rate": test_metrics["win_rate"],
            "out_sample_trades": test_metrics["total_trades"],
            "out_sample_return_pct": test_metrics["total_return_pct"],
        })

    # Aggregate every out-of-sample trade into one honest performance estimate.
    # Pooling all OOS trades gives a stable Sharpe; per-fold Sharpe on a handful
    # of trades is too noisy to compare directly.
    aggregate = _compute_metrics(oos_trades)
    oos_sharpe = aggregate["sharpe_ratio"]

    # Optimistic baseline: the best combo measured on the FULL history (the
    # number the in-sample backtest would proudly report).
    in_sample_best = -1e9
    for combo in COMBINATIONS:
        m = _compute_metrics(_collect_trades(df, combo["filters"], 2, n, atr_mult_sl, atr_mult_tp))
        if m["total_trades"] >= 5:
            in_sample_best = max(in_sample_best, m["sharpe_ratio"])
    if in_sample_best == -1e9:
        in_sample_best = 0.0

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "years_tested": years,
        "n_splits": n_splits,
        "total_bars": n,
        "start_date": str(df["timestamp"].iloc[0]),
        "end_date": str(df["timestamp"].iloc[-1]),
        "folds": folds,
        "walk_forward": aggregate,            # pooled out-of-sample metrics
        "in_sample_best_sharpe": round(in_sample_best, 2),
        "out_sample_sharpe": oos_sharpe,
        # How much the edge decays once it must predict unseen data. A large
        # positive gap = the in-sample result was largely curve-fit.
        "overfitting_gap": round(in_sample_best - oos_sharpe, 2),
        "robust": oos_sharpe > 0 and aggregate["profit_factor"] > 1.0,
        "generated_at": datetime.utcnow().isoformat(),
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
