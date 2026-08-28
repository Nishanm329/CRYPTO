"""
Walk-forward research engine for the strategy loop.

Fixes the lookahead bias present in the legacy combination_backtester
(same-bar-close entry): signals fire on a CLOSED candle i, entry happens
at the OPEN of candle i+1. Trading costs are always applied. Metrics are
computed separately per TRAIN/VALIDATE/HOLDOUT split — never mixed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from indicators import calculate_ema, calculate_rsi, calculate_macd, calculate_adx, calculate_atr

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "data_split.json")

ROUND_TRIP_COST_PCT = 0.30  # 0.15% taker fee + 0.05% slippage, per side x2
MAX_HOLD_BARS = 60          # ~10 days on 4h; avoid infinite holds


def load_split_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_symbol_df(symbol: str, timeframe: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{symbol}_{timeframe}.csv")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema7"] = calculate_ema(df["close"], 7)
    df["ema25"] = calculate_ema(df["close"], 25)
    df["ema50"] = calculate_ema(df["close"], 50)
    df["ema99"] = calculate_ema(df["close"], 99)
    df["ema200"] = calculate_ema(df["close"], 200)
    df["rsi"] = calculate_rsi(df["close"])
    macd, macd_signal, macd_hist = calculate_macd(df["close"])
    df["macd_hist"] = macd_hist
    df["atr"] = calculate_atr(df)
    df["adx"], _, _ = calculate_adx(df)
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma20"]
    return df


def detect_crosses(df: pd.DataFrame, fast_col: str, slow_col: str) -> pd.Series:
    """+1 on bullish cross, -1 on bearish cross, 0 otherwise. Uses only
    data up to and including the current (closed) candle."""
    fast, slow = df[fast_col], df[slow_col]
    diff = fast - slow
    prev_diff = diff.shift(1)
    cross_up = (prev_diff <= 0) & (diff > 0)
    cross_down = (prev_diff >= 0) & (diff < 0)
    out = pd.Series(0, index=df.index)
    out[cross_up] = 1
    out[cross_down] = -1
    return out


def passes_filters(row, filters: list) -> bool:
    for f in filters:
        if f == "adx_trend" and not (row["adx"] > 20):
            return False
        if f == "htf_ema200" and pd.isna(row["ema200"]):
            return False
        if f == "volume_confirm" and not (row["vol_ratio"] > 1.1):
            return False
        if f == "rsi_not_extreme" and not (25 < row["rsi"] < 75):
            return False
    return True


def direction_ok_htf(row, direction: str) -> bool:
    if direction == "LONG":
        return row["close"] > row["ema200"]
    return row["close"] < row["ema200"]


def simulate_variant(df: pd.DataFrame, params: dict) -> list:
    """Returns list of trade dicts: {entry_time, exit_time, direction, r_multiple}."""
    fast_col, slow_col = params["fast_ema"], params["slow_ema"]
    atr_mult_sl = params["atr_mult_sl"]
    rr_target = params["rr_target"]
    filters = params.get("filters", [])

    crosses = detect_crosses(df, fast_col, slow_col)
    trades = []
    n = len(df)
    i = max(df[slow_col].first_valid_index() is not None and 0, 0)

    idx_list = df.index
    for pos in range(1, n - 1):
        c = crosses.iloc[pos]
        if c == 0:
            continue
        direction = "LONG" if c == 1 else "SHORT"
        signal_row = df.iloc[pos]

        if signal_row[["atr", "adx", "rsi", "vol_ratio"]].isna().any():
            continue
        if not passes_filters(signal_row, filters):
            continue
        if "htf_ema200" in filters and not direction_ok_htf(signal_row, direction):
            continue

        entry_pos = pos + 1
        if entry_pos >= n:
            continue
        entry_price = df["open"].iloc[entry_pos]
        atr = signal_row["atr"]
        if atr <= 0 or pd.isna(atr):
            continue
        risk = atr * atr_mult_sl

        if direction == "LONG":
            stop = entry_price - risk
            target = entry_price + risk * rr_target
        else:
            stop = entry_price + risk
            target = entry_price - risk * rr_target

        exit_r = None
        exit_time = None
        for j in range(entry_pos, min(entry_pos + MAX_HOLD_BARS, n)):
            bar = df.iloc[j]
            hit_stop = bar["low"] <= stop if direction == "LONG" else bar["high"] >= stop
            hit_target = bar["high"] >= target if direction == "LONG" else bar["low"] <= target
            if hit_stop and hit_target:
                exit_r = -1.0  # conservative: stop counts first
                exit_time = idx_list[j]
                break
            if hit_stop:
                exit_r = -1.0
                exit_time = idx_list[j]
                break
            if hit_target:
                exit_r = rr_target
                exit_time = idx_list[j]
                break
        if exit_r is None:
            # timed out — mark to market at last available close
            last_close = df["close"].iloc[min(entry_pos + MAX_HOLD_BARS, n) - 1]
            exit_r = (last_close - entry_price) / risk if direction == "LONG" else (entry_price - last_close) / risk
            exit_time = idx_list[min(entry_pos + MAX_HOLD_BARS, n) - 1]

        # Convert round-trip cost (%) into R units using this trade's own risk distance
        cost_r = (ROUND_TRIP_COST_PCT / 100.0 * entry_price) / risk
        exit_r -= cost_r

        trades.append({
            "entry_time": idx_list[entry_pos],
            "exit_time": exit_time,
            "direction": direction,
            "r_multiple": exit_r,
        })
    return trades


def assign_split(trade_time, bounds: dict) -> str:
    t = pd.Timestamp(trade_time)
    if t <= pd.Timestamp(bounds["train_end"]):
        return "train"
    if t <= pd.Timestamp(bounds["validate_end"]):
        return "validate"
    return "holdout"


def compute_metrics(trades: list) -> dict:
    if not trades:
        return {"trades": 0, "expectancy": 0.0, "win_rate": 0.0, "profit_factor": 0.0,
                "max_dd": 0.0, "sharpe": 0.0}
    r = np.array([t["r_multiple"] for t in trades])
    wins = r[r > 0]
    losses = r[r <= 0]
    expectancy = r.mean()
    win_rate = (r > 0).mean() * 100
    profit_factor = (wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else float("inf")
    equity = np.cumsum(r)
    running_max = np.maximum.accumulate(equity) if len(equity) else np.array([0])
    max_dd = float((running_max - equity).max()) if len(equity) else 0.0
    sharpe = (r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0
    return {
        "trades": int(len(r)),
        "expectancy": round(float(expectancy), 4),
        "win_rate": round(float(win_rate), 2),
        "profit_factor": round(float(profit_factor), 3) if profit_factor != float("inf") else 999.0,
        "max_dd": round(max_dd, 3),
        "sharpe": round(float(sharpe), 3),
    }


def run_variant_pooled(params: dict, split_config: dict) -> dict:
    """Run a variant across the whole symbol basket, pooling trades per split."""
    pooled = {"train": [], "validate": [], "holdout": []}
    for symbol in split_config["symbols"]:
        bounds = split_config["per_symbol"][symbol]
        df = load_symbol_df(symbol, split_config["timeframe"])
        df = add_indicators(df)
        trades = simulate_variant(df, params)
        for t in trades:
            split = assign_split(t["entry_time"], bounds)
            pooled[split].append(t)
    return {
        "train": compute_metrics(pooled["train"]),
        "validate": compute_metrics(pooled["validate"]),
        "holdout": compute_metrics(pooled["holdout"]),
        "trades_validate_raw": pooled["validate"],
        "trades_holdout_raw": pooled["holdout"],
    }


def monte_carlo(trade_rs: list, n_paths: int = 2000, seed: int = 42) -> dict:
    if not trade_rs:
        return {"p5_final_r": 0, "p50_final_r": 0, "p95_final_r": 0, "p5_maxdd": 0, "p95_maxdd": 0}
    rng = np.random.default_rng(seed)
    r = np.array(trade_rs)
    n = len(r)
    finals, maxdds = [], []
    for _ in range(n_paths):
        sample = rng.choice(r, size=n, replace=True)
        eq = np.cumsum(sample)
        running_max = np.maximum.accumulate(eq)
        maxdds.append(float((running_max - eq).max()))
        finals.append(float(eq[-1]))
    finals = np.array(finals)
    maxdds = np.array(maxdds)
    return {
        "p5_final_r": round(float(np.percentile(finals, 5)), 2),
        "p50_final_r": round(float(np.percentile(finals, 50)), 2),
        "p95_final_r": round(float(np.percentile(finals, 95)), 2),
        "p5_maxdd": round(float(np.percentile(maxdds, 5)), 2),
        "p95_maxdd": round(float(np.percentile(maxdds, 95)), 2),
    }
