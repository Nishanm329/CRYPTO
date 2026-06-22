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


def calculate_adx(
    df: pd.DataFrame, period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Wilder's ADX with directional indicators.

    Returns (adx, plus_di, minus_di). ADX measures trend *strength* (regime):
    high ADX = trending, low ADX = ranging/chop. +DI/-DI give the direction.
    """
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index
    )
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(com=period - 1, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(com=period - 1, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(com=period - 1, min_periods=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(com=period - 1, min_periods=period).mean()
    return adx, plus_di, minus_di


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tpv = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    return cumulative_tpv / cumulative_vol


def calculate_vwap_bands(
    df: pd.DataFrame, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Volume-weighted standard-deviation bands around VWAP.

    Returns (upper, lower, std). Price stretched beyond a band is statistically
    far from the volume-weighted fair value — a mean-reversion / exhaustion cue.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum().replace(0, np.nan)
    vwap = (typical_price * df["volume"]).cumsum() / cum_vol
    variance = (df["volume"] * (typical_price - vwap) ** 2).cumsum() / cum_vol
    std = np.sqrt(variance)
    return vwap + num_std * std, vwap - num_std * std, std


def calculate_volume_profile(
    df: pd.DataFrame, lookback: int = 120, bins: int = 24
) -> Optional[dict]:
    """Volume Profile over the lookback window.

    Returns dict with Point of Control (poc, the most-traded price level),
    value-area high/low (vah/val, the band containing ~70% of volume), or None.
    """
    recent = df.tail(lookback)
    if len(recent) < 10:
        return None
    lo = float(recent["low"].min())
    hi = float(recent["high"].max())
    if hi <= lo:
        return None
    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    tp = ((recent["high"] + recent["low"] + recent["close"]) / 3).values
    vol = recent["volume"].values
    idx = np.clip(np.digitize(tp, edges) - 1, 0, bins - 1)
    profile = np.zeros(bins)
    np.add.at(profile, idx, vol)
    poc = float(centers[int(np.argmax(profile))])
    total = profile.sum()
    if total <= 0:
        return None
    order = np.argsort(profile)[::-1]
    cum = 0.0
    selected = []
    for o in order:
        selected.append(int(o))
        cum += profile[o]
        if cum >= 0.7 * total:
            break
    return {
        "poc": poc,
        "vah": float(centers[max(selected)]),
        "val": float(centers[min(selected)]),
    }


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


def find_liquidity_levels(
    df: pd.DataFrame, lookback: int = 120, left: int = 3, right: int = 3
) -> Optional[dict]:
    """
    Identify market-structure liquidity pools — the price levels where stop
    orders cluster and forced liquidations get triggered. Buy-side liquidity
    (BSL) rests above recent swing highs; sell-side liquidity (SSL) below recent
    swing lows. Price gravitates to these pools to sweep them, so the nearest
    pool in either direction acts as a magnet / target.

    Real liquidation feeds aren't on Binance's free API, so these pools are
    derived from confirmed swing pivots (the basis of liquidity-sweep analysis).
    Returns nearest pool above/below current price, or None if too little data.
    """
    sub = df.tail(lookback)
    if len(sub) < (left + right + 5):
        return None
    highs = sub["high"].values
    lows = sub["low"].values
    n = len(highs)
    price = float(sub["close"].iloc[-1])

    swing_highs, swing_lows = [], []
    for i in range(left, n - right):
        seg_h = highs[i - left:i + right + 1]
        seg_l = lows[i - left:i + right + 1]
        if highs[i] == seg_h.max():
            swing_highs.append(float(highs[i]))
        if lows[i] == seg_l.min():
            swing_lows.append(float(lows[i]))

    # Buy-side liquidity above price, sell-side below.
    bsl = sorted(h for h in swing_highs if h > price)
    ssl = sorted((l for l in swing_lows if l < price), reverse=True)

    nearest_above = bsl[0] if bsl else None
    nearest_below = ssl[0] if ssl else None
    return {
        "nearest_above": nearest_above,  # buy-side liquidity (short stops/liqs)
        "nearest_below": nearest_below,  # sell-side liquidity (long stops/liqs)
        "buy_side": bsl[:5],
        "sell_side": ssl[:5],
    }


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

    # ADX / directional movement (trend-strength regime filter)
    df["adx"], df["plus_di"], df["minus_di"] = calculate_adx(df)

    # Volume
    df["vol_ratio"] = calculate_volume_ratio(df)
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    # VWAP + volume-weighted std bands
    df["vwap"] = calculate_vwap(df)
    df["vwap_upper"], df["vwap_lower"], df["vwap_std"] = calculate_vwap_bands(df)
    df["vwap_z"] = (df["close"] - df["vwap"]) / df["vwap_std"].replace(0, np.nan)

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


def detect_divergence(
    df: pd.DataFrame, lookback: int = 60, left: int = 3, right: int = 3
) -> Tuple[Optional[str], str]:
    """Detect regular RSI/price divergence over the recent window.

    Returns (direction, description) where direction is:
      'bullish' — price prints a lower low but RSI a higher low (reversal up)
      'bearish' — price prints a higher high but RSI a lower high (reversal down)
      None      — no divergence found.
    Compares the two most recent confirmed price pivots.
    """
    sub = df.tail(lookback)
    if len(sub) < (left + right + 5):
        return None, ""
    close = sub["close"].values
    rsi = sub["rsi"].values
    n = len(close)

    lows, highs = [], []
    for i in range(left, n - right):
        seg = close[i - left:i + right + 1]
        if close[i] == seg.min():
            lows.append(i)
        if close[i] == seg.max():
            highs.append(i)

    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if (close[b] < close[a] and rsi[b] > rsi[a]
                and not np.isnan(rsi[a]) and not np.isnan(rsi[b])):
            return "bullish", f"Price lower-low but RSI higher-low ({rsi[a]:.0f}→{rsi[b]:.0f})"

    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if (close[b] > close[a] and rsi[b] < rsi[a]
                and not np.isnan(rsi[a]) and not np.isnan(rsi[b])):
            return "bearish", f"Price higher-high but RSI lower-high ({rsi[a]:.0f}→{rsi[b]:.0f})"

    return None, ""


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
