"""
Market scanner — scans top Binance USDT pairs for EMA cross signals.
Runs async scans in parallel batches to stay within rate limits.
"""
import asyncio
import time
from typing import List, Optional
from datetime import datetime

from binance_client import get_top_volume_pairs, get_klines, batch_get_tickers, get_fear_greed_index
from signals import generate_signal, HTF_MAP, compute_htf_bias
from models import ScanResult, MarketScanResponse, SignalDirection
from track_record import record_signal

# Rate limiting: Binance allows 1200 weight/min for spot
CONCURRENT_REQUESTS = 8
SCAN_CACHE: dict = {}
CACHE_TTL = 60  # seconds


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


async def scan_market(
    timeframe: str = "1h",
    max_pairs: int = 50,
    min_confidence: int = 50,
    use_cache: bool = True,
) -> MarketScanResponse:
    """
    Main scan function. Scans top USDT pairs and returns ranked signals.
    """
    cache_key = f"{timeframe}_{max_pairs}_{min_confidence}"

    if use_cache and cache_key in SCAN_CACHE:
        cached = SCAN_CACHE[cache_key]
        if time.time() - cached["ts"] < CACHE_TTL:
            return cached["data"]

    t_start = time.time()

    # Get pairs and market data
    pairs = await get_top_volume_pairs(max_pairs)
    ticker_data = await batch_get_tickers(pairs)

    # Get sentiment
    fear_greed = await get_fear_greed_index()
    fg_value = fear_greed.get("value", 50)
    # Normalize fear/greed to -1..+1 sentiment score
    sentiment_score = (fg_value - 50) / 50

    # Scan in batches (respect rate limits)
    all_results: List[ScanResult] = []
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def bounded_scan(sym):
        async with semaphore:
            return await scan_symbol(sym, timeframe, sentiment_score, ticker_data)

    tasks = [bounded_scan(sym) for sym in pairs]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for r in results:
        if r is not None and r.confidence >= min_confidence:
            all_results.append(r)

    # Sort by confidence DESC, then AI probability DESC
    all_results.sort(key=lambda x: (x.confidence, x.ai_probability), reverse=True)

    long_count = sum(1 for r in all_results if r.direction == SignalDirection.LONG)
    short_count = len(all_results) - long_count

    response = MarketScanResponse(
        signals=all_results,
        total_scanned=len(pairs),
        long_count=long_count,
        short_count=short_count,
        scan_duration_ms=round((time.time() - t_start) * 1000, 1),
    )

    SCAN_CACHE[cache_key] = {"ts": time.time(), "data": response}
    return response
