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
    calculate_volume_profile,
    detect_divergence,
    find_liquidity_levels,
)
from models import (
    Signal,
    IndicatorConfirmation,
    IndicatorStatus,
    TakeProfitLevel,
    SignalDirection,
)


# Maps a trading timeframe to the higher timeframe used for trend confirmation.
HTF_MAP = {
    "1m": "15m", "3m": "30m", "5m": "30m", "15m": "1h", "30m": "2h",
    "1h": "4h", "2h": "4h", "4h": "1d", "1d": "1w", "3d": "1w", "1w": None,
}


def compute_htf_bias(htf_df: pd.DataFrame) -> Optional[float]:
    """Higher-timeframe trend bias in [-1, +1] (+ = bullish, - = bearish).

    Combines EMA 7/25 alignment, price vs EMA50, EMA50 vs EMA200 (macro trend)
    and MACD histogram sign. Returns None if there isn't enough data.
    """
    if htf_df is None or len(htf_df) < 50:
        return None
    d = add_all_indicators(htf_df)
    last = d.iloc[-1]
    if d[["ema7", "ema25", "ema50", "ema200"]].iloc[-1].isna().any():
        return None
    score = 0.0
    score += 0.35 if last["ema7"] > last["ema25"] else -0.35
    score += 0.25 if last["close"] > last["ema50"] else -0.25
    score += 0.25 if last["ema50"] > last["ema200"] else -0.25
    score += 0.15 if last["macd_hist"] > 0 else -0.15
    return float(max(-1.0, min(1.0, score)))


def _indicator_status(condition: bool) -> IndicatorStatus:
    return IndicatorStatus.BULLISH if condition else IndicatorStatus.BEARISH


def build_indicator_confirmations(
    df: pd.DataFrame,
    direction: str,
    vol_profile: Optional[dict] = None,
    divergence: Optional[tuple] = None,
    derivatives: Optional[dict] = None,
    order_book: Optional[dict] = None,
    liquidity: Optional[dict] = None,
    onchain: Optional[dict] = None,
    macro: Optional[dict] = None,
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

    # ADX trend-strength regime (with directional DI)
    adx = latest["adx"]
    plus_di = latest["plus_di"]
    minus_di = latest["minus_di"]
    trending = adx >= 20
    di_aligned = (plus_di > minus_di) if is_long else (minus_di > plus_di)
    adx_ok = trending and di_aligned
    confirmations.append(
        IndicatorConfirmation(
            name="ADX (14)",
            value=round(adx, 1) if pd.notna(adx) else 0.0,
            status=_indicator_status(adx_ok),
            description=(
                f"ADX {adx:.1f} — "
                + ("strong trend" if adx >= 30 else "trending" if adx >= 20 else "ranging/chop")
                + (", direction aligned" if di_aligned else ", direction against")
            ),
        )
    )

    # VWAP bands (value relative to volume-weighted fair price)
    vwap = latest["vwap"]
    vwap_z = latest["vwap_z"]
    if pd.notna(vwap_z):
        # Long edge: buying at/below VWAP (value). Short edge: selling above.
        vwap_ok = (price <= vwap) if is_long else (price >= vwap)
        confirmations.append(
            IndicatorConfirmation(
                name="VWAP Bands",
                value=round(vwap_z, 2),
                status=_indicator_status(vwap_ok),
                description=(
                    f"Price {abs(vwap_z):.2f}σ {'above' if vwap_z > 0 else 'below'} VWAP — "
                    + ("stretched/exhaustion" if abs(vwap_z) >= 2 else
                       "value buy" if (is_long and price <= vwap) else
                       "value sell" if (not is_long and price >= vwap) else "chasing")
                ),
            )
        )

    # Volume Profile (Point of Control acceptance)
    if vol_profile:
        poc = vol_profile["poc"]
        vp_ok = (price > poc) if is_long else (price < poc)
        confirmations.append(
            IndicatorConfirmation(
                name="Volume Profile",
                value=round((price - poc) / poc * 100, 2),
                status=_indicator_status(vp_ok),
                description=(
                    f"Price {'above' if price > poc else 'below'} POC ({poc:.6g}); "
                    f"value area {vol_profile['val']:.6g}–{vol_profile['vah']:.6g}"
                ),
            )
        )

    # RSI divergence (reversal confirmation)
    if divergence:
        div_dir, div_desc = divergence
        div_ok = (div_dir == "bullish") if is_long else (div_dir == "bearish")
        confirmations.append(
            IndicatorConfirmation(
                name="RSI Divergence",
                value=1.0 if div_dir else 0.0,
                status=(
                    _indicator_status(div_ok) if div_dir else IndicatorStatus.NEUTRAL
                ),
                description=(div_desc if div_dir else "No divergence detected"),
            )
        )

    # Funding rate (perp leverage / crowd positioning) — contrarian read
    if derivatives and derivatives.get("funding_rate") is not None:
        fr = derivatives["funding_rate"]
        fr_bps = fr * 10000  # basis points for readability
        # Crowded longs (high +funding) favor shorts; crowded shorts favor longs.
        fund_ok = (fr <= 0.0002) if is_long else (fr >= -0.0002)
        confirmations.append(
            IndicatorConfirmation(
                name="Funding Rate",
                value=round(fr_bps, 2),
                status=_indicator_status(fund_ok),
                description=(
                    f"Funding {fr_bps:+.2f} bps — "
                    + ("crowded longs (squeeze risk)" if fr > 0.0005 else
                       "crowded shorts (squeeze fuel)" if fr < -0.0005 else
                       "balanced positioning")
                ),
            )
        )

    # Open interest trend (fresh leverage = conviction behind the move)
    if derivatives and derivatives.get("oi_change_pct") is not None:
        oi = derivatives["oi_change_pct"]
        oi_ok = oi > 0  # rising OI confirms the directional move
        confirmations.append(
            IndicatorConfirmation(
                name="Open Interest",
                value=round(oi, 2),
                status=_indicator_status(oi_ok),
                description=(
                    f"OI {oi:+.1f}% over 24h — "
                    + ("rising, fresh leverage confirms move" if oi > 3 else
                       "falling, positions unwinding" if oi < -3 else
                       "flat, little new conviction")
                ),
            )
        )

    # Order-book imbalance (resting liquidity pressure)
    if order_book and order_book.get("imbalance") is not None:
        imb = order_book["imbalance"]
        ob_ok = (imb > 0.1) if is_long else (imb < -0.1)
        confirmations.append(
            IndicatorConfirmation(
                name="Order Book",
                value=round(imb * 100, 1),
                status=_indicator_status(ob_ok),
                description=(
                    f"Bid/ask imbalance {imb*100:+.0f}% — "
                    + ("strong buy-side depth" if imb > 0.2 else
                       "strong sell-side depth" if imb < -0.2 else
                       "buy-side lean" if imb > 0.05 else
                       "sell-side lean" if imb < -0.05 else "balanced book")
                ),
            )
        )

    # Liquidity pools (liquidation magnet / target in the trade direction)
    if liquidity:
        target = liquidity["nearest_above"] if is_long else liquidity["nearest_below"]
        if target is not None:
            dist = abs(target - price) / price * 100
            # A reachable pool ahead = defined target; absurdly far = weak.
            liq_ok = 0.3 <= dist <= 8.0
            confirmations.append(
                IndicatorConfirmation(
                    name="Liquidity Target",
                    value=round(dist, 2),
                    status=_indicator_status(liq_ok),
                    description=(
                        f"{'Buy-side' if is_long else 'Sell-side'} liquidity at "
                        f"{target:.6g} ({dist:.1f}% {'above' if is_long else 'below'}) — "
                        + ("magnet within reach" if liq_ok else
                           "pool too far" if dist > 8 else "pool already near")
                    ),
                )
            )

    # On-chain / positioning sentiment (smart-money vs crowd, taker flow)
    if onchain:
        global_ls = onchain.get("global_ls")
        top_ls = onchain.get("top_ls")
        taker_ls = onchain.get("taker_ls")
        div = onchain.get("smart_divergence")
        # Smart money positioned with the trade = confirming. When smart traders
        # are more long than the crowd (div > 0) it supports longs; the reverse
        # supports shorts. Fall back to taker flow if divergence is unavailable.
        if div is not None:
            sent_ok = (div > 0) if is_long else (div < 0)
            value = round(div, 2)
            crowd = f"crowd {global_ls:.2f}" if global_ls is not None else ""
            smart = f"smart money {top_ls:.2f}" if top_ls is not None else ""
            desc = (
                f"Top-trader vs crowd L/S divergence {div:+.2f} — "
                + ("smart money leans long" if div > 0.1 else
                   "smart money leans short" if div < -0.1 else
                   "smart money aligned with crowd")
                + (f" ({smart} vs {crowd})" if smart and crowd else "")
            )
        elif taker_ls is not None:
            sent_ok = (taker_ls > 1.0) if is_long else (taker_ls < 1.0)
            value = round(taker_ls, 2)
            desc = (
                f"Taker buy/sell volume ratio {taker_ls:.2f} — "
                + ("aggressive buying" if taker_ls > 1.05 else
                   "aggressive selling" if taker_ls < 0.95 else "balanced flow")
            )
        else:
            sent_ok = None
            value = None
        if value is not None:
            confirmations.append(
                IndicatorConfirmation(
                    name="On-Chain Sentiment",
                    value=value,
                    status=_indicator_status(sent_ok),
                    description=desc,
                )
            )

    # On-chain macro: cycle position (Mayer Multiple) + spot taker flow
    if macro:
        mayer = macro.get("mayer_multiple")
        zone = macro.get("cycle_zone")
        if mayer is not None:
            # Deep value favours longs; overheated favours shorts / warns longs.
            if is_long:
                cyc_ok = mayer < 1.5
            else:
                cyc_ok = mayer > 1.0
            confirmations.append(
                IndicatorConfirmation(
                    name="Cycle (Mayer Mult)",
                    value=round(mayer, 2),
                    status=_indicator_status(cyc_ok),
                    description=(
                        f"Price {mayer:.2f}x its 200-day average — {zone}; "
                        + ("room above value, supports long" if (is_long and mayer < 1.5) else
                           "stretched above value, long is chasing" if is_long else
                           "elevated/distribution zone, supports short" if mayer > 1.0 else
                           "already cheap, short has less room")
                    ),
                )
            )

        bp = macro.get("buy_pressure")
        if bp is not None:
            flow = macro.get("flow_label", "balanced")
            flow_ok = (bp > 0) if is_long else (bp < 0)
            confirmations.append(
                IndicatorConfirmation(
                    name="Spot Flow (CVD)",
                    value=round(bp * 100, 1),
                    status=_indicator_status(flow_ok),
                    description=(
                        f"Net spot taker flow {bp*100:+.1f}% over 14d — {flow} "
                        + ("(market accumulating)" if bp > 0.015 else
                           "(market distributing)" if bp < -0.015 else "(balanced)")
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
    vol_profile: Optional[dict] = None,
    htf_bias: Optional[float] = None,
    divergence: Optional[tuple] = None,
    derivatives: Optional[dict] = None,
    order_book: Optional[dict] = None,
    liquidity: Optional[dict] = None,
    onchain: Optional[dict] = None,
    macro: Optional[dict] = None,
) -> int:
    """
    Score the signal 0–100 as a *normalized weighted composite* of every
    confirmation. Each component yields a quality score in [0, 1]; the result
    is the weight-normalized average × 100. Reaching 100 requires near-perfect
    agreement across all components, so high scores stay rare and the value
    keeps real ranking power (no additive saturation at the ceiling).

    Components that need data not yet available (NaN early bars, no higher
    timeframe, no volume profile) are skipped and the weights renormalized.
    """
    latest = df.iloc[-1]
    is_long = direction == "LONG"
    price = latest["close"]

    components: List[tuple] = []  # (score_0_1, weight)

    # RSI — directional positioning
    rsi = latest["rsi"]
    if is_long:
        r = 1.0 if rsi < 30 else 0.85 if rsi < 45 else 0.6 if rsi < 55 else 0.4 if rsi < 65 else 0.2
    else:
        r = 1.0 if rsi > 70 else 0.85 if rsi > 55 else 0.6 if rsi > 45 else 0.4 if rsi > 35 else 0.2
    components.append((r, 0.10))

    # MACD — directional agreement
    hist = latest["macd_hist"]
    if (is_long and hist > 0) or (not is_long and hist < 0):
        m = 1.0
    elif abs(hist) <= 0.005:
        m = 0.55
    else:
        m = 0.2
    components.append((m, 0.12))

    # Volume — participation behind the move
    vr = latest["vol_ratio"]
    v = 1.0 if vr >= 2.0 else 0.8 if vr >= 1.5 else 0.6 if vr >= 1.2 else 0.4 if vr >= 1.0 else 0.25
    components.append((v, 0.10))

    # Bollinger position
    bb = latest["bb_pct"]
    if is_long:
        b = 1.0 if bb < 0.2 else 0.75 if bb < 0.4 else 0.5 if bb < 0.6 else 0.3
    else:
        b = 1.0 if bb > 0.8 else 0.75 if bb > 0.6 else 0.5 if bb > 0.4 else 0.3
    components.append((b, 0.08))

    # Macro trend (EMA 50/200)
    ema50 = latest["ema50"]
    ema200 = latest["ema200"]
    if is_long:
        t = 1.0 if (price > ema50 > ema200) else 0.7 if price > ema200 else 0.55 if price > ema50 else 0.2
    else:
        t = 1.0 if (price < ema50 < ema200) else 0.7 if price < ema200 else 0.55 if price < ema50 else 0.2
    components.append((t, 0.12))

    # EMA spread — momentum behind the cross
    sp = abs(latest["ema_spread"])
    s = 1.0 if sp > 0.5 else 0.75 if sp > 0.3 else 0.5 if sp > 0.1 else 0.3
    components.append((s, 0.06))

    # ADX regime + directional movement
    adx = latest["adx"]
    plus_di = latest["plus_di"]
    minus_di = latest["minus_di"]
    if pd.notna(adx):
        aligned = (plus_di > minus_di) if is_long else (minus_di > plus_di)
        if aligned and adx >= 30:
            a = 1.0
        elif aligned and adx >= 22:
            a = 0.8
        elif not aligned and adx >= 20:
            a = 0.25  # trending against the signal
        elif adx >= 20:
            a = 0.55
        elif adx < 18:
            a = 0.15  # ranging/chop
        else:
            a = 0.4
        components.append((a, 0.14))

    # VWAP value — entering at/beyond fair value vs chasing
    vwap = latest["vwap"]
    vwap_z = latest["vwap_z"]
    if pd.notna(vwap_z):
        if is_long:
            w = 1.0 if vwap_z <= -1.5 else 0.75 if price <= vwap else 0.2 if vwap_z > 1.5 else 0.5
        else:
            w = 1.0 if vwap_z >= 1.5 else 0.75 if price >= vwap else 0.2 if vwap_z < -1.5 else 0.5
        components.append((w, 0.08))

    # Volume Profile — acceptance relative to POC / value area
    if vol_profile:
        poc, vah, val = vol_profile["poc"], vol_profile["vah"], vol_profile["val"]
        if is_long:
            p = 1.0 if price > vah else 0.75 if price > poc else 0.5 if price > val else 0.25
        else:
            p = 1.0 if price < val else 0.75 if price < poc else 0.5 if price < vah else 0.25
        components.append((p, 0.08))

    # Higher-timeframe trend alignment
    if htf_bias is not None:
        ab = min(1.0, abs(htf_bias))
        if (is_long and htf_bias > 0.15) or (not is_long and htf_bias < -0.15):
            h = 0.7 + 0.3 * ab            # aligned, stronger bias scores higher
        elif (is_long and htf_bias < -0.15) or (not is_long and htf_bias > 0.15):
            h = max(0.05, 0.3 - 0.25 * ab)  # against — the low-win-rate setup
        else:
            h = 0.5
        components.append((h, 0.12))

    # RSI divergence — only scored when a divergence is actually present
    if divergence and divergence[0]:
        div_dir = divergence[0]
        if (is_long and div_dir == "bullish") or (not is_long and div_dir == "bearish"):
            components.append((1.0, 0.10))   # reversal confirms the trade
        else:
            components.append((0.1, 0.10))   # divergence warns against it

    # Funding rate — contrarian crowd positioning
    if derivatives and derivatives.get("funding_rate") is not None:
        fr = derivatives["funding_rate"]
        if is_long:
            # Negative/low funding (no crowded longs) favors a long.
            f = 1.0 if fr <= -0.0005 else 0.75 if fr <= 0.0001 else 0.5 if fr <= 0.0005 else 0.25
        else:
            f = 1.0 if fr >= 0.0005 else 0.75 if fr >= -0.0001 else 0.5 if fr >= -0.0005 else 0.25
        components.append((f, 0.06))

    # Open interest — fresh leverage confirming the move
    if derivatives and derivatives.get("oi_change_pct") is not None:
        oi = derivatives["oi_change_pct"]
        o = 1.0 if oi > 5 else 0.75 if oi > 1 else 0.5 if oi > -1 else 0.3 if oi > -5 else 0.2
        components.append((o, 0.06))

    # Order-book imbalance — resting liquidity pressure in the trade direction
    if order_book and order_book.get("imbalance") is not None:
        imb = order_book["imbalance"] if is_long else -order_book["imbalance"]
        ob = 1.0 if imb > 0.25 else 0.8 if imb > 0.1 else 0.55 if imb > -0.1 else 0.3 if imb > -0.25 else 0.2
        components.append((ob, 0.06))

    # Liquidity target — a reachable pool ahead gives the trade a magnet/target
    if liquidity:
        target = liquidity["nearest_above"] if is_long else liquidity["nearest_below"]
        if target is not None:
            dist = abs(target - price) / price * 100
            lq = 1.0 if 0.5 <= dist <= 4 else 0.7 if dist <= 8 else 0.4 if dist <= 0.5 else 0.3
            components.append((lq, 0.05))

    # On-chain sentiment — smart-money vs crowd positioning (and taker flow)
    if onchain:
        div = onchain.get("smart_divergence")
        taker = onchain.get("taker_ls")
        if div is not None:
            d = div if is_long else -div
            sc = 1.0 if d > 0.2 else 0.8 if d > 0.05 else 0.5 if d > -0.05 else 0.3 if d > -0.2 else 0.2
            components.append((sc, 0.06))
        elif taker is not None:
            t = taker if is_long else (2.0 - taker)
            sc = 1.0 if t > 1.1 else 0.75 if t > 1.0 else 0.5 if t > 0.9 else 0.3
            components.append((sc, 0.06))

    # On-chain macro — cycle position (Mayer) + spot taker flow direction
    if macro:
        mayer = macro.get("mayer_multiple")
        if mayer is not None:
            if is_long:
                mc = 1.0 if mayer < 0.9 else 0.85 if mayer < 1.2 else 0.6 if mayer < 1.6 else 0.35 if mayer < 2.4 else 0.15
            else:
                mc = 1.0 if mayer > 2.4 else 0.8 if mayer > 1.6 else 0.6 if mayer > 1.1 else 0.4 if mayer > 0.9 else 0.2
            components.append((mc, 0.05))
        bp = macro.get("buy_pressure")
        if bp is not None:
            d = bp if is_long else -bp
            fc = 1.0 if d > 0.03 else 0.8 if d > 0.005 else 0.5 if d > -0.005 else 0.3 if d > -0.03 else 0.2
            components.append((fc, 0.05))

    total_w = sum(w for _, w in components)
    weighted = sum(sc * w for sc, w in components) / total_w
    return int(round(weighted * 100))


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
    htf_bias: Optional[float] = None,
    htf_timeframe: Optional[str] = None,
    derivatives: Optional[dict] = None,
    order_book: Optional[dict] = None,
    onchain: Optional[dict] = None,
    macro: Optional[dict] = None,
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

    vol_profile = calculate_volume_profile(df)
    divergence = detect_divergence(df)
    liquidity = find_liquidity_levels(df)
    indicators = build_indicator_confirmations(
        df, direction, vol_profile, divergence, derivatives, order_book,
        liquidity, onchain, macro
    )
    confidence = calculate_confidence(
        df, direction, indicators, vol_profile, htf_bias=htf_bias,
        divergence=divergence, derivatives=derivatives, order_book=order_book,
        liquidity=liquidity, onchain=onchain, macro=macro,
    )
    ai_prob = calculate_ai_probability(df, direction)

    # Multi-timeframe confirmation row (scoring handled inside the composite).
    # Trading against the HTF trend is the classic low-win-rate setup.
    if htf_bias is not None:
        aligned = htf_bias > 0.15 if direction == "LONG" else htf_bias < -0.15
        against = htf_bias < -0.15 if direction == "LONG" else htf_bias > 0.15
        if aligned:
            htf_status = IndicatorStatus.BULLISH
        elif against:
            htf_status = IndicatorStatus.BEARISH
        else:
            htf_status = IndicatorStatus.NEUTRAL
        htf_label = htf_timeframe or "HTF"
        indicators.append(
            IndicatorConfirmation(
                name=f"Higher TF ({htf_label})",
                value=round(htf_bias, 2),
                status=htf_status,
                description=(
                    f"{htf_label} trend bias {htf_bias:+.2f} — "
                    + ("bullish" if htf_bias > 0.15 else "bearish" if htf_bias < -0.15 else "neutral")
                    + (", aligned with signal" if aligned else ", against signal" if against else ", no strong bias")
                ),
            )
        )

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
