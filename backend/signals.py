"""
Signal generation engine.
Combines EMA cross detection with multi-indicator confirmation,
ATR-based risk levels, and AI probability scoring.
"""
import pandas as pd
import numpy as np
from typing import Optional, List
from datetime import datetime

from indicators import (
    add_all_indicators,
    detect_ema_cross,
    detect_support_resistance,
)
from models import (
    Signal,
    IndicatorConfirmation,
    IndicatorStatus,
    TakeProfitLevel,
    SignalDirection,
)


def _indicator_status(condition: bool) -> IndicatorStatus:
    return IndicatorStatus.BULLISH if condition else IndicatorStatus.BEARISH


def build_indicator_confirmations(
    df: pd.DataFrame, direction: str
) -> List[IndicatorConfirmation]:
    """Build the list of indicator confirmations for a signal."""
    latest = df.iloc[-1]
    is_long = direction == "LONG"
    confirmations = []

    # RSI
    rsi = latest["rsi"]
    rsi_bullish = rsi < 55 and rsi > 30
    rsi_bearish = rsi > 45 and rsi < 75
    rsi_ok = rsi_bullish if is_long else rsi_bearish
    confirmations.append(
        IndicatorConfirmation(
            name="RSI (14)",
            value=round(rsi, 1),
            status=_indicator_status(rsi_ok),
            description=(
                f"RSI at {rsi:.1f} — "
                + ("oversold, supports long" if rsi < 40 else
                   "overbought, supports short" if rsi > 60 else
                   "neutral zone")
            ),
        )
    )

    # MACD
    macd = latest["macd"]
    macd_signal = latest["macd_signal"]
    macd_hist = latest["macd_hist"]
    macd_bullish = macd > macd_signal
    macd_ok = macd_bullish if is_long else not macd_bullish
    confirmations.append(
        IndicatorConfirmation(
            name="MACD (12,26,9)",
            value=round(macd_hist, 6),
            status=_indicator_status(macd_ok),
            description=(
                f"MACD {'above' if macd_bullish else 'below'} signal line "
                f"(hist: {macd_hist:+.6f})"
            ),
        )
    )

    # Bollinger Bands
    bb_pct = latest["bb_pct"]
    price = latest["close"]
    bb_lower = latest["bb_lower"]
    bb_upper = latest["bb_upper"]
    bb_bullish = price <= bb_lower * 1.005
    bb_bearish = price >= bb_upper * 0.995
    bb_ok = bb_bullish if is_long else bb_bearish
    confirmations.append(
        IndicatorConfirmation(
            name="Bollinger Bands",
            value=round(bb_pct * 100, 1),
            status=_indicator_status(bb_ok),
            description=(
                f"Price at {bb_pct*100:.0f}% of BB width "
                f"({'near lower band' if bb_pct < 0.2 else 'near upper band' if bb_pct > 0.8 else 'mid-range'})"
            ),
        )
    )

    # Volume
    vol_ratio = latest["vol_ratio"]
    vol_ok = vol_ratio >= 1.3
    confirmations.append(
        IndicatorConfirmation(
            name="Volume",
            value=round(vol_ratio, 2),
            status=_indicator_status(vol_ok),
            description=(
                f"Volume is {vol_ratio:.1f}x the 20-period average "
                f"({'strong' if vol_ratio > 1.5 else 'moderate' if vol_ratio > 1.2 else 'weak'} confirmation)"
            ),
        )
    )

    # EMA alignment (50 and 200)
    ema50 = latest["ema50"]
    ema200 = latest["ema200"]
    trend_bullish = price > ema50 and ema50 > ema200
    trend_bearish = price < ema50 and ema50 < ema200
    trend_ok = trend_bullish if is_long else trend_bearish
    confirmations.append(
        IndicatorConfirmation(
            name="Trend (EMA 50/200)",
            value=round((price - ema200) / ema200 * 100, 2),
            status=_indicator_status(trend_ok),
            description=(
                f"Price is {'above' if price > ema200 else 'below'} EMA200; "
                f"macro trend is {'bullish' if trend_bullish else 'bearish' if trend_bearish else 'mixed'}"
            ),
        )
    )

    # ATR Volatility
    atr_pct = latest["atr_pct"]
    confirmations.append(
        IndicatorConfirmation(
            name="ATR Volatility",
            value=round(atr_pct, 2),
            status=IndicatorStatus.NEUTRAL,
            description=(
                f"ATR is {atr_pct:.2f}% of price — "
                f"{'high' if atr_pct > 3 else 'moderate' if atr_pct > 1.5 else 'low'} volatility"
            ),
        )
    )

    return confirmations


def calculate_confidence(
    df: pd.DataFrame,
    direction: str,
    indicators: List[IndicatorConfirmation],
) -> int:
    """
    Score the signal from 0–100 based on indicator confluence.
    EMA cross is the trigger (50 pts base), other indicators add up to 50 pts.
    Optimized for realistic confidence levels (65-85 for good signals).
    """
    latest = df.iloc[-1]
    is_long = direction == "LONG"
    score = 50  # Base for EMA cross (increased from 40)

    rsi = latest["rsi"]
    macd_hist = latest["macd_hist"]
    vol_ratio = latest["vol_ratio"]
    bb_pct = latest["bb_pct"]
    price = latest["close"]
    ema50 = latest["ema50"]
    ema200 = latest["ema200"]
    ema_spread = abs(latest["ema_spread"])
    roc5 = latest["roc5"]

    # RSI (0-15 pts) - More forgiving thresholds
    if is_long:
        if rsi < 30:
            score += 15  # Deeply oversold
        elif rsi < 45:
            score += 12  # Oversold
        elif rsi < 60:
            score += 8   # Neutral-bullish
        else:
            score += 3   # Overbought but still tradable
    else:
        if rsi > 70:
            score += 15  # Deeply overbought
        elif rsi > 55:
            score += 12  # Overbought
        elif rsi > 40:
            score += 8   # Neutral-bearish
        else:
            score += 3   # Oversold but still tradable

    # MACD (0-12 pts) - More forgiving
    if (is_long and macd_hist > 0) or (not is_long and macd_hist < 0):
        score += 12  # Strong directional agreement
    elif (is_long and macd_hist > -0.005) or (not is_long and macd_hist < 0.005):
        score += 8   # Weak but aligning
    else:
        score += 3   # Neutral

    # Volume spike (0-12 pts) - Increased max
    if vol_ratio >= 2.0:
        score += 12
    elif vol_ratio >= 1.5:
        score += 9
    elif vol_ratio >= 1.2:
        score += 6
    elif vol_ratio >= 1.0:
        score += 3

    # BB position (0-10 pts) - More forgiving
    if is_long and bb_pct < 0.2:
        score += 10  # Near lower band
    elif is_long and bb_pct < 0.4:
        score += 7   # Lower half
    elif is_long and bb_pct < 0.6:
        score += 4   # Middle
    elif not is_long and bb_pct > 0.8:
        score += 10  # Near upper band
    elif not is_long and bb_pct > 0.6:
        score += 7   # Upper half
    elif not is_long and bb_pct > 0.4:
        score += 4   # Middle

    # Macro trend alignment (0-8 pts)
    if is_long and price > ema200:
        score += 8
    elif not is_long and price < ema200:
        score += 8
    elif is_long and price > ema50:
        score += 4   # At least intermediate uptrend
    elif not is_long and price < ema50:
        score += 4   # At least intermediate downtrend

    # EMA spread (momentum of cross, 0-5 pts)
    if ema_spread > 0.5:
        score += 5
    elif ema_spread > 0.3:
        score += 4
    elif ema_spread > 0.1:
        score += 2

    return min(int(score), 100)


def calculate_ai_probability(df: pd.DataFrame, direction: str) -> float:
    """
    Heuristic AI probability score that approximates what an ML classifier
    would output. Uses normalized indicator features to compute a directional
    probability in [0, 1].

    In production, replace this body with inference from a trained
    RandomForest / LGBM / LSTM model.
    """
    latest = df.iloc[-1]
    is_long = direction == "LONG"

    features = {
        "rsi_norm": (latest["rsi"] - 50) / 50,          # -1 to +1
        "macd_hist_sign": np.sign(latest["macd_hist"]),  # -1 or +1
        "bb_pct_centered": latest["bb_pct"] - 0.5,       # -0.5 to +0.5
        "vol_ratio_capped": min(latest["vol_ratio"], 3) / 3,  # 0 to 1
        "ema_spread": latest["ema_spread"] / 2,           # normalized
        "roc5": np.tanh(latest["roc5"] / 5),              # -1 to +1
        "ema7_slope": np.tanh(latest["ema7_slope"] / 2),  # -1 to +1
        "price_vs_vwap": np.tanh((latest["close"] - latest["vwap"]) / latest["vwap"] * 100),
    }

    # Weighted directional score
    weights = {
        "rsi_norm": 0.15,
        "macd_hist_sign": 0.20,
        "bb_pct_centered": 0.15,
        "vol_ratio_capped": 0.15,
        "ema_spread": 0.20,
        "roc5": 0.10,
        "ema7_slope": 0.05,
        "price_vs_vwap": 0.00,
    }

    raw_score = sum(features[k] * weights[k] for k in features)

    # Convert to probability: sigmoid of the directional score
    if is_long:
        prob = 1 / (1 + np.exp(-raw_score * 4))
    else:
        prob = 1 / (1 + np.exp(raw_score * 4))

    # Clamp to reasonable range
    return float(np.clip(prob, 0.35, 0.95))


def calculate_risk_levels(
    df: pd.DataFrame, direction: str, entry: float
) -> tuple:
    """
    Calculate stop loss and take profit levels.
    Uses ATR for dynamic sizing + nearest support/resistance.
    """
    atr = df["atr"].iloc[-1]
    support, resistance = detect_support_resistance(df)

    if direction == "LONG":
        # SL: ATR-based or below support, whichever is tighter
        atr_sl = entry - 2.0 * atr
        sr_sl = support * 0.998
        stop_loss = max(atr_sl, sr_sl)  # tighter (higher) of the two

        # TPs at 1:1, 2:1, 3:1 R:R
        risk = entry - stop_loss
        tp1 = entry + 1.0 * risk
        tp2 = entry + 2.0 * risk
        tp3 = entry + 3.0 * risk

    else:  # SHORT
        atr_sl = entry + 2.0 * atr
        sr_sl = resistance * 1.002
        stop_loss = min(atr_sl, sr_sl)  # tighter (lower) of the two

        risk = stop_loss - entry
        tp1 = entry - 1.0 * risk
        tp2 = entry - 2.0 * risk
        tp3 = entry - 3.0 * risk

    return stop_loss, tp1, tp2, tp3


def generate_signal(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    sentiment_score: float = 0.0,
    min_confidence: int = 65,  # Higher threshold for trading
) -> Optional[Signal]:
    """
    Main signal generation function.
    Returns a Signal object if an EMA cross is detected AND confidence is high enough.

    min_confidence: Only return signals at or above this confidence (default 65% for trading).
                   Use lower values to see all technical setups.
    """
    if len(df) < 50:
        return None

    df = add_all_indicators(df)

    # Check for NaN in critical columns
    if df[["ema7", "ema25", "rsi", "atr"]].iloc[-1].isna().any():
        return None

    direction, candles_since = detect_ema_cross(df)
    if direction is None:
        return None

    latest = df.iloc[-1]
    entry = latest["close"]
    atr = latest["atr"]

    stop_loss, tp1, tp2, tp3 = calculate_risk_levels(df, direction, entry)
    risk = abs(entry - stop_loss)
    if risk == 0:
        return None

    rr_ratio = abs(tp2 - entry) / risk

    indicators = build_indicator_confirmations(df, direction)
    confidence = calculate_confidence(df, direction, indicators)
    ai_prob = calculate_ai_probability(df, direction)

    # Sentiment adjustment (±5 pts to confidence)
    if direction == "LONG" and sentiment_score > 0.2:
        confidence = min(100, confidence + 5)
    elif direction == "SHORT" and sentiment_score < -0.2:
        confidence = min(100, confidence + 5)

    # FILTER: Only return signals with sufficient confidence
    # This dramatically improves win rate by filtering out weak setups
    if confidence < min_confidence:
        return None

    def pct(a, b):
        return round(abs(a - b) / b * 100, 2)

    take_profits = [
        TakeProfitLevel(
            level=1,
            price=round(tp1, 6),
            rr_ratio=1.0,
            pct_gain=pct(tp1, entry),
        ),
        TakeProfitLevel(
            level=2,
            price=round(tp2, 6),
            rr_ratio=2.0,
            pct_gain=pct(tp2, entry),
        ),
        TakeProfitLevel(
            level=3,
            price=round(tp3, 6),
            rr_ratio=3.0,
            pct_gain=pct(tp3, entry),
        ),
    ]

    return Signal(
        symbol=symbol,
        timeframe=timeframe,
        direction=SignalDirection(direction),
        entry_price=round(entry, 6),
        stop_loss=round(stop_loss, 6),
        take_profits=take_profits,
        confidence=confidence,
        ai_probability=round(ai_prob, 4),
        rr_ratio=round(rr_ratio, 2),
        indicators=indicators,
        sentiment_score=round(sentiment_score, 3),
        volume_ratio=round(latest["vol_ratio"], 2),
        atr=round(atr, 6),
        timestamp=datetime.utcnow().isoformat(),
        candles_since_cross=candles_since,
    )
