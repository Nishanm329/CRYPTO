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


async def get_derivatives_dashboard(symbol: str) -> Optional[dict]:
    """
    Aggregate everything the derivatives dashboard needs for one perpetual
    market in a single parallel fetch: current + historical funding, open
    interest (value + trend), long/short positioning (crowd vs smart money),
    and spot order-book imbalance. Returns None if the symbol has no USDⓈ-M
    perpetual market (premiumIndex fails); individual sections may be None.
    """
    client = get_http_client()
    try:
        pi_r, fund_r, oi_r, gls_r, tls_r, tk_r = await asyncio.gather(
            client.get(f"{BINANCE_FUTURES}/fapi/v1/premiumIndex", params={"symbol": symbol}),
            client.get(f"{BINANCE_FUTURES}/fapi/v1/fundingRate", params={"symbol": symbol, "limit": 30}),
            client.get(f"{BINANCE_FUTURES}/futures/data/openInterestHist", params={"symbol": symbol, "period": "1h", "limit": 24}),
            client.get(f"{BINANCE_FUTURES}/futures/data/globalLongShortAccountRatio", params={"symbol": symbol, "period": "1h", "limit": 24}),
            client.get(f"{BINANCE_FUTURES}/futures/data/topLongShortAccountRatio", params={"symbol": symbol, "period": "1h", "limit": 1}),
            client.get(f"{BINANCE_FUTURES}/futures/data/takerlongshortRatio", params={"symbol": symbol, "period": "1h", "limit": 1}),
            return_exceptions=True,
        )
    except Exception:
        return None

    def _json(r):
        try:
            return r.json() if not isinstance(r, Exception) else None
        except Exception:
            return None

    pi = _json(pi_r)
    if not isinstance(pi, dict) or "lastFundingRate" not in pi:
        return None  # no perpetual market for this symbol

    funding_rate = float(pi.get("lastFundingRate", 0.0))
    mark_price = float(pi.get("markPrice", 0.0)) or None
    next_funding_time = int(pi.get("nextFundingTime", 0)) or None

    # Funding history (each interval is ~8h → annualize by ×3×365)
    fund_hist = []
    fh = _json(fund_r)
    if isinstance(fh, list):
        for row in fh:
            try:
                fund_hist.append({"t": int(row["fundingTime"]), "v": float(row["fundingRate"])})
            except Exception:
                continue

    # Open interest: latest USD value + 24h trend + history sparkline
    oi_value, oi_change_pct, oi_hist = None, None, []
    oi = _json(oi_r)
    if isinstance(oi, list) and oi:
        for row in oi:
            try:
                oi_hist.append({"t": int(row["timestamp"]), "v": float(row.get("sumOpenInterestValue", 0))})
            except Exception:
                continue
        try:
            oi_value = float(oi[-1].get("sumOpenInterestValue", 0)) or None
            first = float(oi[0].get("sumOpenInterestValue", 0))
            last = float(oi[-1].get("sumOpenInterestValue", 0))
            if first > 0:
                oi_change_pct = (last - first) / first * 100
        except Exception:
            pass

    # Long/short positioning
    def _last_ratio(data, key):
        if isinstance(data, list) and data:
            try:
                return float(data[-1].get(key, 0)) or None
            except Exception:
                return None
        return None

    gls_data = _json(gls_r)
    global_ls = _last_ratio(gls_data, "longShortRatio")
    top_ls = _last_ratio(_json(tls_r), "longShortRatio")
    taker_ls = _last_ratio(_json(tk_r), "buySellRatio")
    smart_divergence = (top_ls - global_ls) if (global_ls is not None and top_ls is not None) else None

    gls_hist = []
    if isinstance(gls_data, list):
        for row in gls_data:
            try:
                gls_hist.append({"t": int(row["timestamp"]), "v": float(row["longShortRatio"])})
            except Exception:
                continue

    orderbook = await get_orderbook_imbalance(symbol)

    return {
        "symbol": symbol,
        "mark_price": mark_price,
        "funding": {
            "current": funding_rate,
            "annualized_pct": funding_rate * 3 * 365 * 100,
            "next_funding_time": next_funding_time,
            "history": fund_hist,
        },
        "open_interest": {
            "value_usd": oi_value,
            "change_pct_24h": oi_change_pct,
            "history": oi_hist,
        },
        "long_short": {
            "global": global_ls,
            "top": top_ls,
            "taker": taker_ls,
            "smart_divergence": smart_divergence,
            "global_history": gls_hist,
        },
        "orderbook": orderbook,
    }


async def get_liquidation_map(symbol: str) -> Optional[dict]:
    """
    ESTIMATED liquidation-level heatmap.

    Binance offers no free historical liquidation feed, so this is a MODEL — it
    projects where leveraged positions would be force-liquidated by combining:
      • open interest (total notional currently at risk), and
      • a volume-weighted distribution of recent traded prices (a proxy for where
        positions were opened), spread across common leverage tiers (5/10/25/50/100x).
    Long positions liquidate BELOW their entry, shorts ABOVE. Clusters mark price
    zones that tend to act as magnets (cascading stops/liquidations). This is an
    estimate of structure, NOT exact exchange liquidation data.

    Returns None for symbols with no USDⓈ-M perpetual market.
    """
    # Approx maintenance-margin offsets per leverage tier (long, short), and a
    # usage weight (how much OI typically sits at each tier).
    LEV_TIERS = [
        (5, 0.10),
        (10, 0.25),
        (25, 0.30),
        (50, 0.20),
        (100, 0.15),
    ]
    MMR = 0.005  # ~maintenance margin rate, pulls liq slightly toward entry

    client = get_http_client()
    try:
        pi_r, oi_r, klines = await asyncio.gather(
            client.get(f"{BINANCE_FUTURES}/fapi/v1/premiumIndex", params={"symbol": symbol}),
            client.get(f"{BINANCE_FUTURES}/fapi/v1/openInterest", params={"symbol": symbol}),
            get_klines(symbol, "1h", 168),  # 7d hourly = entry-price distribution
            return_exceptions=True,
        )
    except Exception:
        return None

    def _json(r):
        try:
            return r.json() if not isinstance(r, Exception) else None
        except Exception:
            return None

    pi = _json(pi_r)
    if not isinstance(pi, dict) or "markPrice" not in pi:
        return None  # no perpetual market

    mark = float(pi.get("markPrice", 0.0))
    if mark <= 0:
        return None

    oi = _json(oi_r)
    oi_contracts = 0.0
    if isinstance(oi, dict):
        try:
            oi_contracts = float(oi.get("openInterest", 0.0))
        except Exception:
            oi_contracts = 0.0
    oi_notional = oi_contracts * mark  # USDⓈ-M: OI is in base units

    if isinstance(klines, Exception) or klines is None or len(klines) == 0:
        return None

    closes = klines["close"].to_numpy()
    vols = klines["volume"].to_numpy()
    vsum = float(vols.sum()) or 1.0
    weights = vols / vsum  # how much position-building happened at each price

    # Price ladder ±18% around mark, 48 buckets.
    lo, hi = mark * 0.82, mark * 1.18
    nb = 48
    width = (hi - lo) / nb
    long_int = np.zeros(nb)   # long liquidations (downside magnets)
    short_int = np.zeros(nb)  # short liquidations (upside magnets / squeeze fuel)

    def _bucket(price):
        if price < lo or price >= hi:
            return -1
        return int((price - lo) / width)

    for c, w in zip(closes, weights):
        for lev, lw in LEV_TIERS:
            frac = 1.0 / lev - MMR
            long_liq = c * (1.0 - frac)
            short_liq = c * (1.0 + frac)
            bl = _bucket(long_liq)
            if bl >= 0:
                long_int[bl] += w * lw
            bs = _bucket(short_liq)
            if bs >= 0:
                short_int[bs] += w * lw

    total = float(long_int.sum() + short_int.sum()) or 1.0
    peak = float(max(long_int.max(), short_int.max())) or 1.0

    levels = []
    for i in range(nb):
        price = lo + (i + 0.5) * width
        l_notional = (long_int[i] / total) * oi_notional if oi_notional else 0.0
        s_notional = (short_int[i] / total) * oi_notional if oi_notional else 0.0
        levels.append({
            "price": round(price, 8),
            "long": round(float(long_int[i] / peak), 4),   # 0..1 intensity
            "short": round(float(short_int[i] / peak), 4),
            "long_usd": round(l_notional, 0),
            "short_usd": round(s_notional, 0),
        })
    levels.reverse()  # highest price first (top of the ladder)

    # Headline magnets: biggest cluster above and below current price.
    above = [lv for lv in levels if lv["price"] > mark]
    below = [lv for lv in levels if lv["price"] <= mark]
    magnet_up = max(above, key=lambda lv: lv["short"], default=None)
    magnet_down = max(below, key=lambda lv: lv["long"], default=None)

    return {
        "symbol": symbol,
        "mark_price": mark,
        "oi_notional": round(oi_notional, 0) if oi_notional else None,
        "levels": levels,
        "magnet_up": {"price": magnet_up["price"], "usd": magnet_up["short_usd"]} if magnet_up else None,
        "magnet_down": {"price": magnet_down["price"], "usd": magnet_down["long_usd"]} if magnet_down else None,
        "estimated": True,
    }


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
