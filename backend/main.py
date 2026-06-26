from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import logging
import os
import pandas as pd

from binance_client import get_klines, get_fear_greed_index, get_top_volume_pairs, batch_get_tickers, get_derivatives_data, get_orderbook_imbalance, get_onchain_sentiment, get_onchain_macro, get_derivatives_dashboard, get_liquidation_map
from indicators import add_all_indicators, calculate_stoch_rsi
from signals import generate_signal, HTF_MAP, compute_htf_bias
from scanner import scan_market
from track_record import seed_if_empty, evaluate_open, get_stats
import bot_engine
from backtester import run_backtest
from combination_backtester import run_combination_backtest, run_walk_forward_backtest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "3d", "1w"}

# API keys (format "key:user,key2:user2"), matching the auth scheme in
# security.py but without the DB dependency this lightweight service avoids.
_API_KEYS = {
    entry.split(":", 1)[0].strip()
    for entry in os.getenv("API_KEYS", "demo-key-public:demo-user").split(",")
    if ":" in entry
}


def require_api_key(request: Request):
    """Enforce a valid Bearer API key on /api/* routes. Open paths (/, /health)
    and CORS preflight (handled by CORSMiddleware before routing) are exempt."""
    if not request.url.path.startswith("/api/"):
        return
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
    if token not in _API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


app = FastAPI(title="CryptoSignal AI", version="2.0.0", dependencies=[Depends(require_api_key)])
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.upper()
    if not symbol.endswith("USDT"):
        symbol = f"{symbol}USDT"
    return symbol


@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": "production"}

@app.get("/")
async def root():
    return {"message": "CryptoSignal API running"}

@app.get("/api/pairs")
async def get_pairs(limit: int = Query(50, ge=1, le=500)):
    try:
        pairs = await get_top_volume_pairs(n=limit)
        return {"pairs": pairs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tickers")
async def get_tickers(symbols: str = None):
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        sym_list = await get_top_volume_pairs(n=20)
    try:
        data = await batch_get_tickers(sym_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        s: {
            "price": float(data[s]["lastPrice"]),
            "change_24h": float(data[s]["priceChangePercent"]),
            "volume_24h": float(data[s]["quoteVolume"]),
            "high_24h": float(data[s]["highPrice"]),
            "low_24h": float(data[s]["lowPrice"]),
        }
        for s in sym_list
        if s in data
    }

def _safe_val(v, decimals=6):
    if pd.isna(v):
        return None
    return round(float(v), decimals)


# Elliott Wave labels: start point is unlabeled, then 5 impulse + 3 corrective waves.
EW_LABELS = ["", "1", "2", "3", "4", "5", "A", "B", "C"]


def _zigzag_pivots(highs, lows, pct):
    """Percentage-reversal zigzag. Returns chronological [(index, price, 'H'|'L')]."""
    n = len(highs)
    if n < 2:
        return []
    pivots = []
    trend = 1  # 1 = tracking a swing high, -1 = tracking a swing low
    pivot_idx, pivot_price = 0, highs[0]
    for i in range(1, n):
        if trend == 1:
            if highs[i] > pivot_price:
                pivot_idx, pivot_price = i, highs[i]
            elif lows[i] < pivot_price * (1 - pct):
                pivots.append((pivot_idx, pivot_price, "H"))
                trend = -1
                pivot_idx, pivot_price = i, lows[i]
        else:
            if lows[i] < pivot_price:
                pivot_idx, pivot_price = i, lows[i]
            elif highs[i] > pivot_price * (1 + pct):
                pivots.append((pivot_idx, pivot_price, "L"))
                trend = 1
                pivot_idx, pivot_price = i, highs[i]
    pivots.append((pivot_idx, pivot_price, "H" if trend == 1 else "L"))
    return pivots


def detect_elliott_wave(df_reset):
    """Label the most recent zigzag swing structure as an Elliott Wave count.

    Returns (line_points, markers) where line_points is the zigzag polyline and
    markers carries the 1-2-3-4-5/A-B-C labels for the chart.
    """
    n = len(df_reset)
    if n < 10:
        return [], []
    highs = df_reset["high"].astype(float).tolist()
    lows = df_reset["low"].astype(float).tolist()
    times = [int(df_reset.iloc[i]["timestamp"].timestamp()) for i in range(n)]

    # Scale the reversal threshold to recent volatility so the wave count adapts
    # across timeframes and coins instead of using a fixed percentage.
    last_close = float(df_reset["close"].iloc[-1]) or 1.0
    atr = df_reset["atr"].iloc[-1] if "atr" in df_reset.columns else None
    if atr is not None and not pd.isna(atr) and last_close:
        pct = float(atr) / last_close * 3.0
    else:
        pct = 0.03
    pct = max(0.012, min(0.08, pct))

    pivots = _zigzag_pivots(highs, lows, pct)
    if len(pivots) < 3:
        return [], []

    window = pivots[-len(EW_LABELS):]
    labels = EW_LABELS[: len(window)]
    line = [{"time": times[idx], "value": round(price, 6)} for idx, price, _ in window]
    markers = []
    for (idx, price, kind), label in zip(window, labels):
        if not label:
            continue
        markers.append({
            "time": times[idx],
            "position": "aboveBar" if kind == "H" else "belowBar",
            "color": "#eab308",
            "shape": "circle",
            "text": label,
        })
    return line, markers


@app.get("/api/chart/{symbol}")
async def get_chart(symbol: str, timeframe: str = "15m", limit: int = Query(100, ge=50, le=500)):
    symbol = normalize_symbol(symbol)
    try:
        df = await get_klines(symbol, timeframe, limit)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    df = add_all_indicators(df)
    stoch_k, stoch_d = calculate_stoch_rsi(df["rsi"])
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d
    df_reset = df.reset_index()

    bars, volume_data = [], []
    ema7_data, ema25_data = [], []
    bb_upper_data, bb_middle_data, bb_lower_data = [], [], []
    vwap_data, rsi_data = [], []
    macd_data, macd_signal_data, macd_hist_data = [], [], []
    stoch_k_data, stoch_d_data, vol_ma_data = [], [], []

    for _, row in df_reset.iterrows():
        ts = int(row["timestamp"].timestamp())
        bars.append({
            "time": ts,
            "open": round(row["open"], 6),
            "high": round(row["high"], 6),
            "low": round(row["low"], 6),
            "close": round(row["close"], 6),
            "volume": round(row["volume"], 2),
        })
        is_up = row["close"] >= row["open"]
        volume_data.append({
            "time": ts,
            "value": round(row["volume"], 2),
            "color": "rgba(34,197,94,0.5)" if is_up else "rgba(239,68,68,0.5)",
        })
        if _safe_val(row["ema7"]) is not None:
            ema7_data.append({"time": ts, "value": _safe_val(row["ema7"])})
        if _safe_val(row["ema25"]) is not None:
            ema25_data.append({"time": ts, "value": _safe_val(row["ema25"])})
        if _safe_val(row["bb_upper"]) is not None:
            bb_upper_data.append({"time": ts, "value": _safe_val(row["bb_upper"])})
            bb_middle_data.append({"time": ts, "value": _safe_val(row["bb_middle"])})
            bb_lower_data.append({"time": ts, "value": _safe_val(row["bb_lower"])})
        if _safe_val(row["vwap"]) is not None:
            vwap_data.append({"time": ts, "value": _safe_val(row["vwap"])})
        if _safe_val(row["rsi"], 2) is not None:
            rsi_data.append({"time": ts, "value": _safe_val(row["rsi"], 2)})
        if _safe_val(row["macd"], 8) is not None:
            macd_data.append({"time": ts, "value": _safe_val(row["macd"], 8)})
            macd_signal_data.append({"time": ts, "value": _safe_val(row["macd_signal"], 8)})
            hist_val = _safe_val(row["macd_hist"], 8)
            macd_hist_data.append({"time": ts, "value": hist_val, "color": "#22c55e" if (hist_val or 0) >= 0 else "#ef4444"})
        if _safe_val(row["stoch_k"], 2) is not None:
            stoch_k_data.append({"time": ts, "value": _safe_val(row["stoch_k"], 2)})
        if _safe_val(row["stoch_d"], 2) is not None:
            stoch_d_data.append({"time": ts, "value": _safe_val(row["stoch_d"], 2)})
        if _safe_val(row["vol_ma20"], 2) is not None:
            vol_ma_data.append({"time": ts, "value": _safe_val(row["vol_ma20"], 2)})

    signal_markers = []
    for i in range(1, len(df_reset)):
        prev, curr = df_reset.iloc[i - 1], df_reset.iloc[i]
        if pd.isna(prev["ema7"]) or pd.isna(curr["ema7"]):
            continue
        ts = int(curr["timestamp"].timestamp())
        prev_above = prev["ema7"] > prev["ema25"]
        curr_above = curr["ema7"] > curr["ema25"]
        if not prev_above and curr_above:
            signal_markers.append({"time": ts, "position": "belowBar", "color": "#22c55e", "shape": "arrowUp"})
        elif prev_above and not curr_above:
            signal_markers.append({"time": ts, "position": "aboveBar", "color": "#ef4444", "shape": "arrowDown"})

    elliott_wave, elliott_wave_markers = detect_elliott_wave(df_reset)

    latest = df_reset.iloc[-1]
    latest_values = {
        "ema7": _safe_val(latest.get("ema7")),
        "ema25": _safe_val(latest.get("ema25")),
        "vwap": _safe_val(latest.get("vwap")),
        "bb_upper": _safe_val(latest.get("bb_upper")),
        "bb_middle": _safe_val(latest.get("bb_middle")),
        "bb_lower": _safe_val(latest.get("bb_lower")),
        "rsi": _safe_val(latest.get("rsi"), 2),
        "macd": _safe_val(latest.get("macd"), 8),
        "macd_signal": _safe_val(latest.get("macd_signal"), 8),
        "macd_hist": _safe_val(latest.get("macd_hist"), 8),
        "stoch_k": _safe_val(latest.get("stoch_k"), 2),
        "stoch_d": _safe_val(latest.get("stoch_d"), 2),
        "vol_ratio": _safe_val(latest.get("vol_ratio"), 2),
        "atr": _safe_val(latest.get("atr")),
    }

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": bars,
        "ema7": ema7_data,
        "ema25": ema25_data,
        "bb_upper": bb_upper_data,
        "bb_middle": bb_middle_data,
        "bb_lower": bb_lower_data,
        "vwap": vwap_data,
        "rsi": rsi_data,
        "macd": macd_data,
        "macd_signal": macd_signal_data,
        "macd_hist": macd_hist_data,
        "stoch_k": stoch_k_data,
        "stoch_d": stoch_d_data,
        "volume": volume_data,
        "vol_ma": vol_ma_data,
        "signals": signal_markers,
        "elliott_wave": elliott_wave,
        "elliott_wave_markers": elliott_wave_markers,
        "latest_values": latest_values,
    }

@app.get("/api/signal/{symbol}")
async def get_signal(symbol: str, timeframe: str = "15m"):
    symbol = normalize_symbol(symbol)
    htf_tf = HTF_MAP.get(timeframe)

    # All of these data sources are independent inputs to generate_signal, so
    # fetch them concurrently instead of serially (was ~7 sequential round-trips).
    df, fg, htf_df, derivatives, order_book, onchain, macro = await asyncio.gather(
        get_klines(symbol, timeframe, 300),
        get_fear_greed_index(),
        get_klines(symbol, htf_tf, 300) if htf_tf else asyncio.sleep(0, result=None),
        get_derivatives_data(symbol),
        get_orderbook_imbalance(symbol),
        get_onchain_sentiment(symbol),
        get_onchain_macro(symbol),
        return_exceptions=True,
    )

    # The primary kline series is required — a failure here is a 404.
    if isinstance(df, Exception):
        raise HTTPException(status_code=404, detail=str(df))

    # Sentiment (degrade to neutral on failure).
    sentiment_score = 0.0
    if not isinstance(fg, Exception) and fg:
        sentiment_score = (fg.get("value", 50) - 50) / 50

    # Higher-timeframe trend confirmation (optional).
    htf_bias = None
    if htf_tf and not isinstance(htf_df, Exception) and htf_df is not None:
        try:
            htf_bias = compute_htf_bias(htf_df)
        except Exception:
            htf_bias = None

    # Remaining context sources are optional — drop any that errored.
    derivatives = None if isinstance(derivatives, Exception) else derivatives
    order_book = None if isinstance(order_book, Exception) else order_book
    onchain = None if isinstance(onchain, Exception) else onchain
    macro = None if isinstance(macro, Exception) else macro

    # min_confidence=0 so the user always sees the technical setup for the
    # symbol they explicitly selected (the scanner applies its own filter).
    signal = generate_signal(
        df, symbol, timeframe, sentiment_score, min_confidence=0,
        htf_bias=htf_bias, htf_timeframe=htf_tf, derivatives=derivatives,
        order_book=order_book, onchain=onchain, macro=macro,
    )
    if signal is None:
        return None
    return signal

@app.get("/api/scan")
async def scan_signals(
    timeframe: str = "1h",
    max_pairs: int = Query(50, ge=10, le=200),
    min_confidence: int = Query(45, ge=0, le=100),
):
    try:
        return await scan_market(timeframe, max_pairs, min_confidence, use_cache=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/{symbol}")
async def backtest(
    symbol: str,
    timeframe: str = Query("1h"),
    limit: int = Query(500, ge=100, le=1000),
    atr_sl: float = Query(2.0, ge=0.5, le=5.0),
    atr_tp: float = Query(3.0, ge=1.0, le=10.0),
):
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    symbol = normalize_symbol(symbol)
    try:
        return await run_backtest(symbol, timeframe, atr_sl, atr_tp, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/combinations/{symbol}")
async def backtest_combinations(
    symbol: str,
    timeframe: str = Query("1d"),
    years: int = Query(6, ge=1, le=10),
    atr_sl: float = Query(2.0, ge=0.5, le=5.0),
    atr_tp: float = Query(3.0, ge=1.0, le=10.0),
):
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    symbol = normalize_symbol(symbol)
    try:
        return await run_combination_backtest(symbol, timeframe, years, atr_sl, atr_tp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/walk-forward/{symbol}")
async def backtest_walk_forward(
    symbol: str,
    timeframe: str = Query("1d"),
    years: int = Query(6, ge=1, le=10),
    n_splits: int = Query(5, ge=2, le=10),
    atr_sl: float = Query(2.0, ge=0.5, le=5.0),
    atr_tp: float = Query(3.0, ge=1.0, le=10.0),
):
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    symbol = normalize_symbol(symbol)
    try:
        return await run_walk_forward_backtest(symbol, timeframe, years, n_splits, atr_sl, atr_tp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/track-record")
async def track_record():
    """Verified, forward-tested performance of published signals.

    On first call, seeds from recent history so the record is populated; every
    call refreshes open positions against fresh price action (throttled)."""
    try:
        await seed_if_empty()
        await evaluate_open()
        return get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BotCreate(BaseModel):
    mode: str = "grid"
    symbol: str = "BTCUSDT"
    timeframe: str = "1h"
    config: dict = {}


@app.get("/api/bots")
async def bots_list():
    """List paper-trading bots, refreshing each against fresh price action."""
    try:
        bots = await bot_engine.list_bots()
        return {"bots": bots, "summary": bot_engine.get_summary()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bots")
async def bots_create(body: BotCreate):
    if body.timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    symbol = normalize_symbol(body.symbol)
    try:
        return await bot_engine.create_bot(body.mode, symbol, body.timeframe, body.config or {})
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bots/{bot_id}/stop")
async def bots_stop(bot_id: str):
    if not bot_engine.stop_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"ok": True}


@app.post("/api/bots/{bot_id}/start")
async def bots_start(bot_id: str):
    if not bot_engine.start_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"ok": True}


@app.delete("/api/bots/{bot_id}")
async def bots_delete(bot_id: str):
    if not bot_engine.delete_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"ok": True}


@app.get("/api/trading/keys/status")
async def trading_keys_status():
    # Live trading is not configured in this deployment; report no stored
    # credentials so the Settings UI shows the unconfigured state cleanly.
    return {"has_credentials": False}


@app.get("/api/sentiment")
async def get_sentiment():
    try:
        fg = await get_fear_greed_index()
    except Exception:
        fg = {"value": 50, "classification": "Neutral"}
    score = (fg.get("value", 50) - 50) / 50
    return {
        "fear_greed": fg,
        "overall_score": round(score, 3),
        "classification": fg.get("classification", "Neutral"),
    }

@app.get("/api/derivatives/{symbol}")
async def get_derivatives(symbol: str):
    """Derivatives dashboard for one perpetual market: funding (current +
    history), open interest (value + trend), long/short positioning, order-book
    imbalance. 404 if the symbol has no USDⓈ-M perpetual market."""
    symbol = normalize_symbol(symbol)
    data = await get_derivatives_dashboard(symbol)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No perpetual market for {symbol}")
    return data

@app.get("/api/liquidations/{symbol}")
async def get_liquidations(symbol: str):
    """Estimated liquidation-level heatmap (model from open interest + recent
    price distribution across leverage tiers — NOT exchange liquidation data).
    404 if the symbol has no USDⓈ-M perpetual market."""
    symbol = normalize_symbol(symbol)
    data = await get_liquidation_map(symbol)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No perpetual market for {symbol}")
    return data

@app.get("/api/market-overview")
async def get_market_overview():
    try:
        ticker_data = await batch_get_tickers(["BTCUSDT", "ETHUSDT"])
    except Exception as e:
        logger.error(f"[market-overview] ticker fetch failed: {e}")
        ticker_data = {}

    try:
        fg = await get_fear_greed_index()
    except Exception:
        fg = {"value": 50, "classification": "Neutral"}

    btc = ticker_data.get("BTCUSDT", {})
    eth = ticker_data.get("ETHUSDT", {})

    btc_price = float(btc.get("lastPrice", 0) or 0)
    btc_change = float(btc.get("priceChangePercent", 0) or 0)
    eth_price = float(eth.get("lastPrice", 0) or 0)
    eth_change = float(eth.get("priceChangePercent", 0) or 0)

    btc_d = 54.0 + (btc_change - eth_change) * 0.2 if (btc_price and eth_price) else 54.0
    btc_d = round(max(40, min(70, btc_d)), 2)
    total_mcap = round(btc_price * 19700000 / btc_d * 100 / 1e12, 2) if btc_d else 0

    return {
        "btc": {
            "price": round(btc_price, 2),
            "change_24h": round(btc_change, 2),
            "volume_24h": round(float(btc.get("quoteVolume", 0) or 0) / 1e9, 2),
        },
        "eth": {
            "price": round(eth_price, 2),
            "change_24h": round(eth_change, 2),
            "volume_24h": round(float(eth.get("quoteVolume", 0) or 0) / 1e9, 2),
        },
        "btc_dominance": btc_d,
        "btc_dominance_change": round((btc_change - eth_change) * 0.1, 2),
        "total_mcap_trillions": total_mcap,
        "total_mcap_change": round((btc_change + eth_change) / 2, 2),
        "fear_greed": fg,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
