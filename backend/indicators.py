"""
Technical indicator calculations.
All functions operate on a pandas DataFrame with OHLCV columns.
"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional


def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tpv = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    return cumulative_tpv / cumulative_vol


def calculate_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    avg_volume = df["volume"].rolling(window=period).mean()
    return df["volume"] / avg_volume


def detect_support_resistance(df: pd.DataFrame, lookback: int = 50) -> Tuple[float, float]:
    """Simple pivot-based support/resistance detection."""
    recent = df.tail(lookback)
    resistance = recent["high"].max()
    support = recent["low"].min()

    # Refine: find the most-tested price levels
    highs = recent["high"].values
    lows = recent["low"].values

    # Cluster nearby levels
    def cluster_levels(levels, tolerance_pct=0.005):
        if len(levels) == 0:
            return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for l in levels[1:]:
            if abs(l - clusters[-1][-1]) / clusters[-1][-1] <= tolerance_pct:
                clusters[-1].append(l)
            else:
                clusters.append([l])
        return [np.mean(c) for c in clusters]

    resistance_levels = cluster_levels(highs)
    support_levels = cluster_levels(lows)

    current = df["close"].iloc[-1]
    nearest_resistance = min(
        (r for r in resistance_levels if r > current), default=resistance
    )
    nearest_support = max(
        (s for s in support_levels if s < current), default=support
    )
    return nearest_support, nearest_resistance


def calculate_stoch_rsi(
    rsi: pd.Series, period: int = 14, smooth_k: int = 3, smooth_d: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """Stochastic RSI — %K and %D lines."""
    lowest_rsi = rsi.rolling(window=period).min()
    highest_rsi = rsi.rolling(window=period).max()
    rsi_range = highest_rsi - lowest_rsi
    stoch_rsi = (rsi - lowest_rsi) / rsi_range.replace(0, np.nan) * 100
    k = stoch_rsi.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    return k, d


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to the DataFrame."""
    df = df.copy()

    # EMAs (core signal)
    df["ema7"] = calculate_ema(df["close"], 7)
    df["ema25"] = calculate_ema(df["close"], 25)
    df["ema50"] = calculate_ema(df["close"], 50)
    df["ema200"] = calculate_ema(df["close"], 200)

    # RSI
    df["rsi"] = calculate_rsi(df["close"])

    # MACD
    df["macd"], df["macd_signal"], df["macd_hist"] = calculate_macd(df["close"])

    # Bollinger Bands
    df["bb_upper"], df["bb_middle"], df["bb_lower"] = calculate_bollinger_bands(df["close"])
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # ATR
    df["atr"] = calculate_atr(df)
    df["atr_pct"] = df["atr"] / df["close"] * 100

    # Volume
    df["vol_ratio"] = calculate_volume_ratio(df)
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    # VWAP
    df["vwap"] = calculate_vwap(df)

    # Price momentum
    df["roc5"] = df["close"].pct_change(5) * 100   # 5-bar ROC
    df["roc10"] = df["close"].pct_change(10) * 100

    # EMA slope (normalized)
    df["ema7_slope"] = df["ema7"].pct_change(3) * 100
    df["ema25_slope"] = df["ema25"].pct_change(3) * 100

    # Distance from EMAs
    df["dist_ema7"] = (df["close"] - df["ema7"]) / df["ema7"] * 100
    df["dist_ema25"] = (df["close"] - df["ema25"]) / df["ema25"] * 100

    # EMA spread (7 vs 25)
    df["ema_spread"] = (df["ema7"] - df["ema25"]) / df["ema25"] * 100

    return df


def detect_ema_cross(df: pd.DataFrame) -> Tuple[Optional[str], int]:
    """
    Detect EMA 7/25 crossover.
    Returns (direction, candles_since_cross) where direction is 'LONG', 'SHORT', or None.
    candles_since_cross=0 means the cross just happened on the latest candle.
    """
    ema7 = df["ema7"]
    ema25 = df["ema25"]

    # Look back up to 5 candles for a recent cross
    for i in range(1, min(6, len(df))):
        idx_now = -i
        idx_prev = -(i + 1)

        curr_above = ema7.iloc[idx_now] > ema25.iloc[idx_now]
        prev_above = ema7.iloc[idx_prev] > ema25.iloc[idx_prev]

        if not prev_above and curr_above:
            return "LONG", i - 1
        elif prev_above and not curr_above:
            return "SHORT", i - 1

    return None, -1
