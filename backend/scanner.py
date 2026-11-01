"""
Market scanner — scans top Binance USDT pairs for EMA cross signals.
Runs async scans in parallel batches to stay within rate limits.
"""
import asyncio
import time
from typing import List, Optional
from datetime import datetime

import pandas as pd

from binance_client import (
    get_top_volume_pairs, get_top_btc_volume_pairs, get_klines, batch_get_tickers, get_fear_greed_index,
)
from signals import generate_signal, HTF_MAP, compute_htf_bias
from indicators import (
    add_all_indicators,
    add_ema_columns,
    add_rsi_columns,
    detect_ema_precross,
    detect_divergence,
)
from models import (
    ScanResult, MarketScanResponse, SignalDirection, PreCrossAlert, PreCrossScanResponse,
    DivergenceAlert, DivergenceScanResponse,
)
from track_record import record_signal
from logging_config import get_logger

logger = get_logger(__name__)

# Rate limiting: Binance allows 1200 weight/min for spot. Kline calls are weight
# 1-2 each, so a 100-pair scan (~200 calls) is still within budget at this concurrency.
CONCURRENT_REQUESTS = 16
# Cache stores the FULL, unfiltered scan keyed by "{timeframe}_{max_pairs}", so a
# single expensive compute serves every min_confidence (filtering is applied at read
# time). A background warmer keeps the hot timeframes fresh; cold callers get a
# non-blocking "warming" response instead of waiting ~40s for a live 100-pair scan.
SCAN_CACHE: dict = {}
CACHE_TTL = 90  # seconds
_inflight: dict = {}  # key -> asyncio.Task, dedupes concurrent refreshes of the same scan


async def scan_symbol(
    symbol: str,
    timeframe: str,
    sentiment_score: float,
    ticker_data: dict,
) -> Optional[ScanResult]:
    """Scan a single symbol and return a ScanResult if a signal is found."""
    try:
        df = await get_klines(symbol, timeframe, limit=200)

        # Higher-timeframe trend confirmation
        htf_tf = HTF_MAP.get(timeframe)
        htf_bias = None
        if htf_tf:
            try:
                htf_df = await get_klines(symbol, htf_tf, limit=200)
                htf_bias = compute_htf_bias(htf_df)
            except Exception:
                htf_bias = None

        # No gate here — scan_market applies the user's min_confidence filter.
        signal = generate_signal(
            df, symbol, timeframe, sentiment_score, min_confidence=0,
            htf_bias=htf_bias, htf_timeframe=htf_tf,
        )

        if signal is None:
            return None

        # Log publishable signals to the verified track record (deduped + forward-tested later).
        record_signal(signal)

        ticker = ticker_data.get(symbol, {})
        price = float(ticker.get("lastPrice", df["close"].iloc[-1]))
        change_24h = float(ticker.get("priceChangePercent", 0))
        volume_24h = float(ticker.get("quoteVolume", 0))

        return ScanResult(
            symbol=symbol,
            timeframe=timeframe,
            direction=signal.direction,
            confidence=signal.confidence,
            ai_probability=signal.ai_probability,
            price=price,
            change_24h=change_24h,
            volume_24h=volume_24h,
            rr_ratio=signal.rr_ratio,
            timestamp=signal.timestamp,
        )
    except Exception as e:
        return None


async def _compute_scan(timeframe: str, max_pairs: int) -> dict:
    """Run a full scan and return all (unfiltered) results sorted by confidence."""
    t_start = time.time()

    pairs = await get_top_volume_pairs(max_pairs)
    ticker_data = await batch_get_tickers(pairs)

    fear_greed = await get_fear_greed_index()
    fg_value = fear_greed.get("value", 50)
    sentiment_score = (fg_value - 50) / 50  # normalize to -1..+1

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def bounded_scan(sym):
        async with semaphore:
            return await scan_symbol(sym, timeframe, sentiment_score, ticker_data)

    results = await asyncio.gather(*[bounded_scan(s) for s in pairs], return_exceptions=False)
    all_results = [r for r in results if r is not None]
    all_results.sort(key=lambda x: (x.confidence, x.ai_probability), reverse=True)

    return {
        "results": all_results,
        "total_scanned": len(pairs),
        "scan_duration_ms": round((time.time() - t_start) * 1000, 1),
    }


async def scan_btc_symbol(
    symbol: str,
    timeframe: str,
    sentiment_score: float,
    ticker_data: dict,
) -> Optional[ScanResult]:
    """Same as scan_symbol, but for a BTC-quoted pair (e.g. ETHBTC) — an altcoin's
    signal relative to BTC rather than to the dollar. Deliberately does NOT call
    record_signal(): the Track Record's win-rate stats are for actionable
    USDT-denominated trades, and mixing in a different quote asset would corrupt
    that ledger rather than extend it."""
    try:
        df = await get_klines(symbol, timeframe, limit=200)

        htf_tf = HTF_MAP.get(timeframe)
        htf_bias = None
        if htf_tf:
            try:
                htf_df = await get_klines(symbol, htf_tf, limit=200)
                htf_bias = compute_htf_bias(htf_df)
            except Exception:
                htf_bias = None

        signal = generate_signal(
            df, symbol, timeframe, sentiment_score, min_confidence=0,
            htf_bias=htf_bias, htf_timeframe=htf_tf,
        )
        if signal is None:
            return None

        ticker = ticker_data.get(symbol, {})
        price = float(ticker.get("lastPrice", df["close"].iloc[-1]))
        change_24h = float(ticker.get("priceChangePercent", 0))
        volume_24h = float(ticker.get("quoteVolume", 0))

        return ScanResult(
            symbol=symbol,
            timeframe=timeframe,
            direction=signal.direction,
            confidence=signal.confidence,
            ai_probability=signal.ai_probability,
            price=price,
            change_24h=change_24h,
            volume_24h=volume_24h,
            rr_ratio=signal.rr_ratio,
            timestamp=signal.timestamp,
        )
    except Exception:
        return None


BTC_SCAN_CACHE: dict = {}
_btc_inflight: dict = {}


async def _compute_btc_scan(timeframe: str, max_pairs: int) -> dict:
    t_start = time.time()
    pairs = await get_top_btc_volume_pairs(max_pairs)
    ticker_data = await batch_get_tickers(pairs)

    fear_greed = await get_fear_greed_index()
    fg_value = fear_greed.get("value", 50)
    sentiment_score = (fg_value - 50) / 50

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def bounded_scan(sym):
        async with semaphore:
            return await scan_btc_symbol(sym, timeframe, sentiment_score, ticker_data)

    results = await asyncio.gather(*[bounded_scan(s) for s in pairs], return_exceptions=False)
    all_results = [r for r in results if r is not None]
    all_results.sort(key=lambda x: (x.confidence, x.ai_probability), reverse=True)

    return {
        "results": all_results,
        "total_scanned": len(pairs),
        "scan_duration_ms": round((time.time() - t_start) * 1000, 1),
    }


async def refresh_btc_scan(timeframe: str, max_pairs: int) -> dict:
    """Mirrors refresh_scan()'s cache-stampede protection, scoped to the BTC scan cache."""
    key = f"{timeframe}_{max_pairs}"
    existing = _btc_inflight.get(key)
    if existing is not None and not existing.done():
        return await existing

    task = asyncio.ensure_future(_compute_btc_scan(timeframe, max_pairs))
    _btc_inflight[key] = task
    try:
        data = await task
        BTC_SCAN_CACHE[key] = {"ts": time.time(), **data}
        return data
    finally:
        _btc_inflight.pop(key, None)


async def scan_btc_market(
    timeframe: str = "1d",
    max_pairs: int = 100,
    min_confidence: int = 50,
    use_cache: bool = True,
) -> MarketScanResponse:
    """Same cache-first / stale-while-revalidate pattern as scan_market(), scoped
    to the BTC-quoted pair universe (altcoins vs BTC rather than vs USDT)."""
    key = f"{timeframe}_{max_pairs}"
    entry = BTC_SCAN_CACHE.get(key)

    if use_cache and entry is not None:
        if time.time() - entry["ts"] >= CACHE_TTL:
            asyncio.ensure_future(refresh_btc_scan(timeframe, max_pairs))
        return _build_response(entry, min_confidence)

    asyncio.ensure_future(refresh_btc_scan(timeframe, max_pairs))
    return MarketScanResponse(
        signals=[], total_scanned=0, long_count=0, short_count=0,
        scan_duration_ms=0, warming=True,
    )


async def refresh_scan(timeframe: str, max_pairs: int) -> dict:
    """Compute the full scan and store it in the cache. Concurrent callers for the
    same (timeframe, max_pairs) share a single in-flight run (no cache stampede)."""
    key = f"{timeframe}_{max_pairs}"
    existing = _inflight.get(key)
    if existing is not None and not existing.done():
        return await existing

    task = asyncio.ensure_future(_compute_scan(timeframe, max_pairs))
    _inflight[key] = task
    try:
        data = await task
        SCAN_CACHE[key] = {"ts": time.time(), **data}
        return data
    finally:
        _inflight.pop(key, None)


def _build_response(entry: dict, min_confidence: int, warming: bool = False) -> MarketScanResponse:
    """Apply the user's confidence filter to a cached full-scan entry."""
    results = [r for r in entry["results"] if r.confidence >= min_confidence]
    long_count = sum(1 for r in results if r.direction == SignalDirection.LONG)
    return MarketScanResponse(
        signals=results,
        total_scanned=entry["total_scanned"],
        long_count=long_count,
        short_count=len(results) - long_count,
        scan_duration_ms=entry.get("scan_duration_ms", 0),
        warming=warming,
    )


async def scan_market(
    timeframe: str = "1h",
    max_pairs: int = 50,
    min_confidence: int = 50,
    use_cache: bool = True,
) -> MarketScanResponse:
    """Return ranked signals. Serves instantly from the full-scan cache (filtering by
    min_confidence at read time); a stale entry is served while a refresh runs in the
    background. A fully cold cache returns a non-blocking `warming` response so the
    request never blocks ~40s on a live large scan (which would hit the proxy timeout)."""
    key = f"{timeframe}_{max_pairs}"
    entry = SCAN_CACHE.get(key)

    if use_cache and entry is not None:
        if time.time() - entry["ts"] >= CACHE_TTL:
            asyncio.ensure_future(refresh_scan(timeframe, max_pairs))  # stale-while-revalidate
        return _build_response(entry, min_confidence)

    # Cold cache: kick off the compute in the background and tell the caller to poll again.
    asyncio.ensure_future(refresh_scan(timeframe, max_pairs))
    return MarketScanResponse(
        signals=[], total_scanned=0, long_count=0, short_count=0,
        scan_duration_ms=0, warming=True,
    )


# ── EMA pre-cross (convergence) scanning ────────────────────────────────────
# Mirrors the scan_market cache pattern above, but flags symbols whose EMA
# 7/25 gap is closing and within threshold_pct — i.e. a cross may be about
# to happen, not one that already has.
PRECROSS_CACHE: dict = {}
PRECROSS_CACHE_TTL = 90
_precross_inflight: dict = {}


async def scan_precross_symbol(
    symbol: str,
    timeframe: str,
    threshold_pct: float,
    ticker_data: dict,
) -> Optional[PreCrossAlert]:
    try:
        df = await get_klines(symbol, timeframe, limit=200)
        if len(df) < 50:
            return None
        # Only the EMA cross geometry is read below — skip the full indicator
        # suite (~19x cheaper per symbol across a 100-pair scan).
        df = add_ema_columns(df)
        if pd.isna(df["ema7"].iloc[-1]) or pd.isna(df["ema25"].iloc[-1]):
            return None

        result = detect_ema_precross(df, threshold_pct=threshold_pct)
        if result is None:
            return None

        ticker = ticker_data.get(symbol, {})
        price = float(ticker.get("lastPrice", df["close"].iloc[-1]))
        change_24h = float(ticker.get("priceChangePercent", 0))
        volume_24h = float(ticker.get("quoteVolume", 0))

        return PreCrossAlert(
            symbol=symbol,
            timeframe=timeframe,
            direction=SignalDirection(result["direction"]),
            price=price,
            spread_pct=result["spread_pct"],
            threshold_pct=threshold_pct,
            change_24h=change_24h,
            volume_24h=volume_24h,
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception:
        # One bad symbol must not sink the whole scan, but stay visible:
        # silently returning None makes a real bug look like "no alerts".
        logger.warning("pre-cross scan failed for %s (%s)", symbol, timeframe, exc_info=True)
        return None


async def _compute_precross_scan(timeframe: str, max_pairs: int, threshold_pct: float) -> dict:
    t_start = time.time()

    pairs = await get_top_volume_pairs(max_pairs)
    ticker_data = await batch_get_tickers(pairs)

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def bounded_scan(sym):
        async with semaphore:
            return await scan_precross_symbol(sym, timeframe, threshold_pct, ticker_data)

    results = await asyncio.gather(*[bounded_scan(s) for s in pairs], return_exceptions=False)
    alerts = [r for r in results if r is not None]
    alerts.sort(key=lambda x: x.spread_pct)  # closest to crossing first

    return {
        "alerts": alerts,
        "total_scanned": len(pairs),
        "scan_duration_ms": round((time.time() - t_start) * 1000, 1),
    }


async def refresh_precross_scan(timeframe: str, max_pairs: int, threshold_pct: float) -> dict:
    key = f"{timeframe}_{max_pairs}_{threshold_pct}"
    existing = _precross_inflight.get(key)
    if existing is not None and not existing.done():
        return await existing

    task = asyncio.ensure_future(_compute_precross_scan(timeframe, max_pairs, threshold_pct))
    _precross_inflight[key] = task
    try:
        data = await task
        PRECROSS_CACHE[key] = {"ts": time.time(), **data}
        return data
    finally:
        _precross_inflight.pop(key, None)


async def scan_precross_market(
    timeframe: str = "1d",
    max_pairs: int = 50,
    threshold_pct: float = 5.0,
    use_cache: bool = True,
) -> PreCrossScanResponse:
    key = f"{timeframe}_{max_pairs}_{threshold_pct}"
    entry = PRECROSS_CACHE.get(key)

    if use_cache and entry is not None:
        if time.time() - entry["ts"] >= PRECROSS_CACHE_TTL:
            asyncio.ensure_future(refresh_precross_scan(timeframe, max_pairs, threshold_pct))
        return PreCrossScanResponse(
            alerts=entry["alerts"],
            total_scanned=entry["total_scanned"],
            timeframe=timeframe,
            threshold_pct=threshold_pct,
            scan_duration_ms=entry.get("scan_duration_ms", 0),
            warming=False,
        )

    asyncio.ensure_future(refresh_precross_scan(timeframe, max_pairs, threshold_pct))
    return PreCrossScanResponse(
        alerts=[], total_scanned=0, timeframe=timeframe, threshold_pct=threshold_pct,
        scan_duration_ms=0, warming=True,
    )


# ── RSI/price divergence (standalone alert) ─────────────────────────────────
# A reversal signal in its own right, not gated on an EMA cross. Uses a short
# lookback so only recently-confirmed pivots surface (a divergence from deep
# in the window is stale and no longer actionable).
DIVERGENCE_CACHE: dict = {}
DIVERGENCE_CACHE_TTL = 90
_divergence_inflight: dict = {}
DIVERGENCE_LOOKBACK = 20


async def scan_divergence_symbol(
    symbol: str,
    timeframe: str,
    ticker_data: dict,
) -> Optional[DivergenceAlert]:
    try:
        df = await get_klines(symbol, timeframe, limit=200)
        if len(df) < 50:
            return None
        # detect_divergence reads only close + rsi — skip the full suite.
        df = add_rsi_columns(df)
        if pd.isna(df["rsi"].iloc[-1]):
            return None

        direction, desc = detect_divergence(df, lookback=DIVERGENCE_LOOKBACK)
        if direction is None:
            return None

        ticker = ticker_data.get(symbol, {})
        price = float(ticker.get("lastPrice", df["close"].iloc[-1]))
        change_24h = float(ticker.get("priceChangePercent", 0))
        volume_24h = float(ticker.get("quoteVolume", 0))

        return DivergenceAlert(
            symbol=symbol,
            timeframe=timeframe,
            direction=SignalDirection.LONG if direction == "bullish" else SignalDirection.SHORT,
            price=price,
            rsi=round(float(df["rsi"].iloc[-1]), 1),
            description=desc,
            change_24h=change_24h,
            volume_24h=volume_24h,
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception:
        logger.warning("divergence scan failed for %s (%s)", symbol, timeframe, exc_info=True)
        return None


async def _compute_divergence_scan(timeframe: str, max_pairs: int) -> dict:
    t_start = time.time()

    pairs = await get_top_volume_pairs(max_pairs)
    ticker_data = await batch_get_tickers(pairs)

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def bounded_scan(sym):
        async with semaphore:
            return await scan_divergence_symbol(sym, timeframe, ticker_data)

    results = await asyncio.gather(*[bounded_scan(s) for s in pairs], return_exceptions=False)
    alerts = [r for r in results if r is not None]
    alerts.sort(key=lambda x: x.volume_24h, reverse=True)

    return {
        "alerts": alerts,
        "total_scanned": len(pairs),
        "scan_duration_ms": round((time.time() - t_start) * 1000, 1),
    }


async def refresh_divergence_scan(timeframe: str, max_pairs: int) -> dict:
    key = f"{timeframe}_{max_pairs}"
    existing = _divergence_inflight.get(key)
    if existing is not None and not existing.done():
        return await existing

    task = asyncio.ensure_future(_compute_divergence_scan(timeframe, max_pairs))
    _divergence_inflight[key] = task
    try:
        data = await task
        DIVERGENCE_CACHE[key] = {"ts": time.time(), **data}
        return data
    finally:
        _divergence_inflight.pop(key, None)


async def scan_divergence_market(
    timeframe: str = "1h",
    max_pairs: int = 50,
    use_cache: bool = True,
) -> DivergenceScanResponse:
    key = f"{timeframe}_{max_pairs}"
    entry = DIVERGENCE_CACHE.get(key)

    if use_cache and entry is not None:
        if time.time() - entry["ts"] >= DIVERGENCE_CACHE_TTL:
            asyncio.ensure_future(refresh_divergence_scan(timeframe, max_pairs))
        return DivergenceScanResponse(
            alerts=entry["alerts"],
            total_scanned=entry["total_scanned"],
            timeframe=timeframe,
            scan_duration_ms=entry.get("scan_duration_ms", 0),
            warming=False,
        )

    asyncio.ensure_future(refresh_divergence_scan(timeframe, max_pairs))
    return DivergenceScanResponse(
        alerts=[], total_scanned=0, timeframe=timeframe, scan_duration_ms=0, warming=True,
    )
