"""
Binance API client — pulls real market data from public endpoints.
No API key required for market data.
"""
import httpx
import asyncio
from typing import List, Optional
import pandas as pd
import numpy as np
from datetime import datetime

BINANCE_BASE = "https://api.binance.com"
BINANCE_FUTURES = "https://fapi.binance.com"
FEAR_GREED_API = "https://api.alternative.me/fng/"

# Cache to avoid hammering Binance
_pair_cache: List[str] = []
_pair_cache_ts: float = 0
_CACHE_TTL = 300  # seconds


async def get_all_usdt_pairs(min_volume_usdt: float = 1_000_000) -> List[str]:
    """Return all actively trading USDT spot pairs on Binance."""
    global _pair_cache, _pair_cache_ts
    import time

    if _pair_cache and (time.time() - _pair_cache_ts) < _CACHE_TTL:
        return _pair_cache

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BINANCE_BASE}/api/v3/exchangeInfo")
        info = resp.json()

        # Get 24h tickers for volume filter
        ticker_resp = await client.get(f"{BINANCE_BASE}/api/v3/ticker/24hr")
        ticker_data = ticker_resp.json()

        # Handle error responses or empty results
        if isinstance(ticker_data, dict) and "code" in ticker_data:
            # API error response, fallback to empty tickers
            tickers = {}
        elif isinstance(ticker_data, list):
            tickers = {t["symbol"]: float(t.get("quoteVolume", 0)) for t in ticker_data if "symbol" in t}
        else:
            tickers = {}

        pairs = []
        for s in info["symbols"]:
            if (
                s["quoteAsset"] == "USDT"
                and s["status"] == "TRADING"
                and s["isSpotTradingAllowed"]
            ):
                vol = tickers.get(s["symbol"], 0)
                if vol >= min_volume_usdt:
                    pairs.append(s["symbol"])

    # Sort by volume descending
    pairs.sort(key=lambda p: tickers.get(p, 0), reverse=True)
    _pair_cache = pairs
    _pair_cache_ts = time.time()
    return pairs


async def get_klines(
    symbol: str, interval: str, limit: int = 300
) -> pd.DataFrame:
    """Fetch OHLCV candlestick data from Binance."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BINANCE_BASE}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        data = resp.json()

    if not data or isinstance(data, dict):
        raise ValueError(f"No kline data for {symbol} {interval}")

    df = pd.DataFrame(
        data,
        columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore",
        ],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = df[col].astype(float)
    df.set_index("timestamp", inplace=True)
    return df


async def get_historical_klines(
    symbol: str, interval: str, start_ms: int, end_ms: Optional[int] = None
) -> "pd.DataFrame":
    """
    Fetch all klines from start_ms to end_ms using pagination.
    start_ms / end_ms are unix timestamps in milliseconds.
    Handles Binance's 1000-candle-per-request limit automatically.
    """
    all_data = []
    current_start = start_ms

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "limit": 1000,
            }
            if end_ms:
                params["endTime"] = end_ms

            resp = await client.get(f"{BINANCE_BASE}/api/v3/klines", params=params)
            data = resp.json()

            if not data or isinstance(data, dict):
                break

            all_data.extend(data)

            if len(data) < 1000:
                break  # received last page

            # Next page starts after the close_time of the last bar + 1 ms
            current_start = int(data[-1][6]) + 1
            await asyncio.sleep(0.1)  # stay within rate limits

    if not all_data:
        raise ValueError(f"No historical data for {symbol} {interval}")

    df = pd.DataFrame(
        all_data,
        columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore",
        ],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = df[col].astype(float)
    df.set_index("timestamp", inplace=True)
    return df


async def get_ticker_24h(symbol: Optional[str] = None) -> dict:
    """Get 24-hour price statistics."""
    async with httpx.AsyncClient(timeout=10) as client:
        params = {}
        if symbol:
            params["symbol"] = symbol
        resp = await client.get(
            f"{BINANCE_BASE}/api/v3/ticker/24hr", params=params
        )
        return resp.json()


async def get_fear_greed_index() -> dict:
    """Fetch the Crypto Fear & Greed Index from alternative.me (free, no key)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{FEAR_GREED_API}?limit=1")
            data = resp.json()
            entry = data["data"][0]
            return {
                "value": int(entry["value"]),
                "classification": entry["value_classification"],
                "timestamp": datetime.fromtimestamp(
                    int(entry["timestamp"])
                ).isoformat(),
            }
    except Exception:
        # Fallback if API is down
        return {
            "value": 50,
            "classification": "Neutral",
            "timestamp": datetime.utcnow().isoformat(),
        }


async def get_top_volume_pairs(n: int = 50) -> List[str]:
    """Return top N USDT pairs by 24h quote volume."""
    pairs = await get_all_usdt_pairs()
    return pairs[:n]


async def batch_get_tickers(symbols: List[str]) -> dict:
    """Fetch ticker data for multiple symbols efficiently."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BINANCE_BASE}/api/v3/ticker/24hr")
        all_tickers = resp.json()
        symbol_set = set(symbols)
        return {
            t["symbol"]: t
            for t in all_tickers
            if t["symbol"] in symbol_set
        }
