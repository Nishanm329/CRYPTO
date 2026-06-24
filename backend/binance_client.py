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

# Stablecoins to filter out (no price movement)
STABLECOINS = {
    "USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "FRAX",
    "USDE", "EURC", "EURS", "EURT", "GBPT", "JPYT",
    "FDUSD", "MATIC", "GRAI", "USD1",  # All pegged to ~$1.00
}

# Cache to avoid hammering Binance
_pair_cache: List[str] = []
_pair_cache_ts: float = 0
_CACHE_TTL = 300  # seconds

# Shared pooled HTTP client — reused across calls so we don't pay a fresh TLS
# handshake on every request (a single scan makes ~40 kline calls).
_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=15,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _http_client


async def get_all_usdt_pairs(min_volume_usdt: float = 1_000_000) -> List[str]:
    """Return all actively trading USDT spot pairs on Binance."""
    global _pair_cache, _pair_cache_ts
    import time

    if _pair_cache and (time.time() - _pair_cache_ts) < _CACHE_TTL:
        return _pair_cache

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BINANCE_BASE}/api/v3/exchangeInfo")
        info = resp.json()

        # Handle error/rate-limit responses (no "symbols" key) by falling back to last good cache
        if not isinstance(info, dict) or "symbols" not in info:
            return _pair_cache or []

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
            base_asset = s.get("baseAsset", "")

            # Skip stablecoin-to-stablecoin pairs (no price movement)
            if base_asset in STABLECOINS:
                continue

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
    client = get_http_client()
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


async def get_derivatives_data(symbol: str) -> Optional[dict]:
    """
    Fetch funding rate + open-interest trend from Binance USDⓈ-M perpetual
    futures. Returns None if the symbol has no perpetual market (many small
    spot pairs don't), so callers should treat it as optional context.

    funding_rate   — latest funding rate (e.g. +0.0001 = +0.01%). Positive
                     means longs pay shorts (crowded longs); negative means
                     shorts pay longs (crowded shorts).
    oi_change_pct  — % change in open interest over the last ~24h. Rising OI
                     means fresh leverage entering (conviction behind the move).
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            pi_resp, oi_resp = await asyncio.gather(
                client.get(
                    f"{BINANCE_FUTURES}/fapi/v1/premiumIndex",
                    params={"symbol": symbol},
                ),
                client.get(
                    f"{BINANCE_FUTURES}/futures/data/openInterestHist",
                    params={"symbol": symbol, "period": "1h", "limit": 24},
                ),
            )

        pi = pi_resp.json()
        if not isinstance(pi, dict) or "lastFundingRate" not in pi:
            return None
        funding_rate = float(pi.get("lastFundingRate", 0.0))

        oi_change_pct = None
        oi = oi_resp.json()
        if isinstance(oi, list) and len(oi) >= 2:
            first = float(oi[0].get("sumOpenInterest", 0))
            last = float(oi[-1].get("sumOpenInterest", 0))
            if first > 0:
                oi_change_pct = (last - first) / first * 100

        return {"funding_rate": funding_rate, "oi_change_pct": oi_change_pct}
    except Exception:
        return None


async def get_orderbook_imbalance(symbol: str, limit: int = 100) -> Optional[dict]:
    """
    Fetch the spot order book and measure bid/ask imbalance in the top `limit`
    levels. Returns imbalance in [-1, +1]: positive = resting buy pressure
    (more bid liquidity), negative = sell pressure. None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BINANCE_BASE}/api/v3/depth",
                params={"symbol": symbol, "limit": limit},
            )
        d = resp.json()
        if not isinstance(d, dict) or "bids" not in d or "asks" not in d:
            return None
        bid_vol = sum(float(p) * float(q) for p, q in d["bids"])
        ask_vol = sum(float(p) * float(q) for p, q in d["asks"])
        total = bid_vol + ask_vol
        if total <= 0:
            return None
        return {
            "imbalance": (bid_vol - ask_vol) / total,
            "bid_vol": bid_vol,
            "ask_vol": ask_vol,
        }
    except Exception:
        return None


async def get_onchain_sentiment(symbol: str) -> Optional[dict]:
    """
    Fetch positioning/flow sentiment from Binance USDⓈ-M futures free data
    endpoints as an on-chain / market-sentiment proxy. Returns None for
    spot-only symbols without a perpetual market, so treat it as optional.

    global_ls        — global long/short account ratio (retail crowd positioning).
                       >1 = more accounts long than short.
    top_ls           — top-trader long/short account ratio (smart-money positioning).
    taker_ls         — taker buy/sell volume ratio (aggressive order flow);
                       >1 = market buying into asks, <1 = selling into bids.
    smart_divergence — top_ls - global_ls. Positive = smart money more long than
                       the crowd (bullish tell); negative = crowd more long than
                       smart money (contrarian bearish, crowded-long risk).
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            g_resp, t_resp, tk_resp = await asyncio.gather(
                client.get(
                    f"{BINANCE_FUTURES}/futures/data/globalLongShortAccountRatio",
                    params={"symbol": symbol, "period": "1h", "limit": 1},
                ),
                client.get(
                    f"{BINANCE_FUTURES}/futures/data/topLongShortAccountRatio",
                    params={"symbol": symbol, "period": "1h", "limit": 1},
                ),
                client.get(
                    f"{BINANCE_FUTURES}/futures/data/takerlongshortRatio",
                    params={"symbol": symbol, "period": "1h", "limit": 1},
                ),
            )

        def _last_ratio(resp, key):
            data = resp.json()
            if isinstance(data, list) and data:
                return float(data[-1].get(key, 0)) or None
            return None

        global_ls = _last_ratio(g_resp, "longShortRatio")
        top_ls = _last_ratio(t_resp, "longShortRatio")
        taker_ls = _last_ratio(tk_resp, "buySellRatio")

        if global_ls is None and top_ls is None and taker_ls is None:
            return None

        smart_divergence = None
        if global_ls is not None and top_ls is not None:
            smart_divergence = top_ls - global_ls

        return {
            "global_ls": global_ls,
            "top_ls": top_ls,
            "taker_ls": taker_ls,
            "smart_divergence": smart_divergence,
        }
    except Exception:
        return None


async def get_onchain_macro(symbol: str) -> Optional[dict]:
    """
    Free on-chain-style macro context computed from Binance daily klines.

    True on-chain feeds (Glassnode MVRV, exchange net-flows) require paid APIs,
    so this derives the same edge from public spot data:

    mayer_multiple — price / 200-day SMA. The Mayer Multiple is a widely-used
                     cycle-position metric (the free MVRV cousin). >2.4 = market
                     historically overheated (caution on new longs); <1.0 = deep
                     value (longs favoured). cycle_zone is the labelled bucket.
    buy_pressure   — net spot taker buy fraction over the last 14 daily bars minus
                     0.5. Positive = aggressive market buying (accumulation, the
                     free exchange-net-flow proxy); negative = distribution.
    flow_label     — "accumulation" / "distribution" / "balanced".

    Returns None if there isn't enough daily history.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": "1d", "limit": 250},
            )
        data = resp.json()
        if not isinstance(data, list) or len(data) < 60:
            return None

        closes = np.array([float(d[4]) for d in data])
        quote_vol = np.array([float(d[7]) for d in data])
        taker_buy_quote = np.array([float(d[10]) for d in data])

        price = float(closes[-1])
        window = min(200, len(closes))
        sma = float(closes[-window:].mean())
        mayer = price / sma if sma > 0 else None
        if mayer is None:
            return None

        if mayer >= 2.4:
            cycle_zone = "overheated"
        elif mayer >= 1.5:
            cycle_zone = "elevated"
        elif mayer >= 1.0:
            cycle_zone = "fair value"
        elif mayer >= 0.8:
            cycle_zone = "undervalued"
        else:
            cycle_zone = "deep value"

        n = min(14, len(taker_buy_quote))
        tot_v = float(quote_vol[-n:].sum())
        buy_pressure = None
        flow_label = "balanced"
        if tot_v > 0:
            buy_frac = float(taker_buy_quote[-n:].sum()) / tot_v
            buy_pressure = buy_frac - 0.5
            if buy_pressure > 0.015:
                flow_label = "accumulation"
            elif buy_pressure < -0.015:
                flow_label = "distribution"

        return {
            "mayer_multiple": round(mayer, 3),
            "cycle_zone": cycle_zone,
            "buy_pressure": round(buy_pressure, 4) if buy_pressure is not None else None,
            "flow_label": flow_label,
        }
    except Exception:
        return None


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
