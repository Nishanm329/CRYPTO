"""
Kronos scanner mode — ranks the top Binance USDT pairs by the Kronos model's
forecast of where price will be `pred_len` candles from now.

Kronos inference is slow (seconds per pair on GPU, tens of seconds on CPU) and
the forecaster runs one inference at a time, so this scan is far heavier than
the EMA scan. It therefore:

  * runs entirely in the background and returns immediately with `warming=True`
    plus progress, so the UI polls instead of holding a request open;
  * publishes partial results as each pair finishes, so the list fills in live;
  * caches a finished scan for one candle of the chosen timeframe (5 min – 1 h).

Each result is cross-referenced with the cached EMA scan for the same
timeframe, so the UI can show whether Kronos agrees with the EMA signal.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from binance_client import get_top_volume_pairs, batch_get_tickers, get_klines
import kronos_forecaster
import scanner

logger = logging.getLogger(__name__)

DEFAULT_PAIRS = 20
MAX_PAIRS = 100
DEFAULT_PRED_LEN = 24
LOOKBACK = 400  # candles of history fed to the model (within Kronos-small's 512 context)

# key -> {"ts", "done", "total", "results", "complete", "started", "duration_ms", "errors"}
KRONOS_SCAN_CACHE: dict = {}
_inflight: dict = {}


def _key(timeframe: str, max_pairs: int, pred_len: int) -> str:
    return f"{timeframe}_{max_pairs}_{pred_len}"


def cache_ttl(timeframe: str) -> float:
    """A forecast is stale once a new candle closes: cache for one bar, 5 min – 1 h."""
    return max(300.0, min(3600.0, kronos_forecaster.interval_delta(timeframe).total_seconds()))


def _ema_signals(timeframe: str) -> dict:
    """symbol -> EMA ScanResult from any cached EMA scan for this timeframe."""
    out: dict = {}
    for key, entry in scanner.SCAN_CACHE.items():
        if key.startswith(f"{timeframe}_"):
            for r in entry.get("results", []):
                prev = out.get(r.symbol)
                if prev is None or r.confidence > prev.confidence:
                    out[r.symbol] = r
    return out


def _agreement(kronos_dir: str, ema_dir: Optional[str]) -> Optional[bool]:
    if ema_dir is None or kronos_dir == "FLAT":
        return None
    return (kronos_dir == "UP") == (ema_dir == "LONG")


def _attach_ema(result: dict, ema: dict) -> dict:
    sig = ema.get(result["symbol"])
    ema_dir = sig.direction.value if sig is not None else None
    return {
        **result,
        "ema_direction": ema_dir,
        "ema_confidence": sig.confidence if sig is not None else None,
        "agrees_with_ema": _agreement(result["direction"], ema_dir),
    }


async def _forecast_symbol(symbol: str, timeframe: str, pred_len: int, ticker: dict) -> dict:
    df = await get_klines(symbol, timeframe, LOOKBACK)
    pred = await asyncio.to_thread(kronos_forecaster.forecast, df, timeframe, pred_len, 1)
    last_close = float(df["close"].iloc[-1])
    s = kronos_forecaster.summarize(last_close, pred)
    return {
        "symbol": symbol,
        "price": float(ticker.get("lastPrice", last_close)),
        "change_24h": float(ticker.get("priceChangePercent", 0)),
        "volume_24h": float(ticker.get("quoteVolume", 0)),
        "pred_close": s["pred_close"],
        "pred_change_pct": s["change_pct"],
        "pred_high": s["pred_high"],
        "pred_low": s["pred_low"],
        # Biggest swing either way inside the forecast window, as % of last close.
        "pred_upside_pct": round((s["pred_high"] / last_close - 1) * 100, 3) if last_close else 0.0,
        "pred_downside_pct": round((s["pred_low"] / last_close - 1) * 100, 3) if last_close else 0.0,
        "direction": s["direction"],
    }


async def _run_scan(timeframe: str, max_pairs: int, pred_len: int) -> None:
    key = _key(timeframe, max_pairs, pred_len)
    started = time.time()
    entry = {
        "ts": started, "started": started, "done": 0, "total": 0,
        "results": [], "errors": 0, "complete": False, "duration_ms": 0.0,
    }
    # Keep serving the previous complete scan (if any) until this one finishes.
    previous = KRONOS_SCAN_CACHE.get(key)
    if previous is None or not previous.get("complete"):
        KRONOS_SCAN_CACHE[key] = entry

    pairs = await get_top_volume_pairs(max_pairs)
    tickers = await batch_get_tickers(pairs)
    entry["total"] = len(pairs)

    # Pairs run one after another: the model holds a lock per inference anyway,
    # and sequential order means the highest-volume pairs fill in first.
    for symbol in pairs:
        try:
            entry["results"].append(
                await _forecast_symbol(symbol, timeframe, pred_len, tickers.get(symbol, {}))
            )
        except kronos_forecaster.KronosUnavailable:
            raise
        except Exception as e:  # one bad pair shouldn't sink the scan
            entry["errors"] += 1
            logger.debug("Kronos scan skipped %s: %s", symbol, e)
        entry["done"] += 1

    entry["complete"] = True
    entry["ts"] = time.time()
    entry["duration_ms"] = round((time.time() - started) * 1000, 1)
    KRONOS_SCAN_CACHE[key] = entry


async def _run_guarded(timeframe: str, max_pairs: int, pred_len: int) -> None:
    key = _key(timeframe, max_pairs, pred_len)
    try:
        await _run_scan(timeframe, max_pairs, pred_len)
    except kronos_forecaster.KronosUnavailable as e:
        KRONOS_SCAN_CACHE.pop(key, None)
        logger.warning("Kronos scan aborted: %s", e)
    except Exception:
        logger.exception("Kronos scan failed for %s", key)
        entry = KRONOS_SCAN_CACHE.get(key)
        if entry is not None and not entry.get("complete"):
            KRONOS_SCAN_CACHE.pop(key, None)
    finally:
        _inflight.pop(key, None)


def _start(timeframe: str, max_pairs: int, pred_len: int) -> None:
    key = _key(timeframe, max_pairs, pred_len)
    task = _inflight.get(key)
    if task is None or task.done():
        _inflight[key] = asyncio.ensure_future(_run_guarded(timeframe, max_pairs, pred_len))


def _response(timeframe: str, pred_len: int, entry: Optional[dict], warming: bool, refreshing: bool) -> dict:
    ema = _ema_signals(timeframe)
    results = [_attach_ema(r, ema) for r in (entry or {}).get("results", [])]
    results.sort(key=lambda r: abs(r["pred_change_pct"]), reverse=True)
    up = sum(1 for r in results if r["direction"] == "UP")
    down = sum(1 for r in results if r["direction"] == "DOWN")
    return {
        "available": True,
        "model": kronos_forecaster.MODEL_NAME,
        "timeframe": timeframe,
        "pred_len": pred_len,
        "warming": warming,
        "refreshing": refreshing,
        "progress": {
            "done": (entry or {}).get("done", 0),
            "total": (entry or {}).get("total", 0),
        },
        "results": results,
        "up_count": up,
        "down_count": down,
        "flat_count": len(results) - up - down,
        "errors": (entry or {}).get("errors", 0),
        "scan_duration_ms": (entry or {}).get("duration_ms", 0.0),
        "generated_at": int((entry or {}).get("ts", time.time())),
        "disclaimer": "Model forecast, not financial advice. Sampling-based and uncertain.",
    }


async def scan_kronos(
    timeframe: str = "1h",
    max_pairs: int = DEFAULT_PAIRS,
    pred_len: int = DEFAULT_PRED_LEN,
) -> dict:
    """Non-blocking: returns the cached (or partial) scan and starts/refreshes it
    in the background. Raises KronosUnavailable if Kronos isn't installed."""
    kronos_forecaster.interval_delta(timeframe)  # ValueError on a bad timeframe
    st = kronos_forecaster.status()
    if not st["available"]:
        raise kronos_forecaster.KronosUnavailable(
            st.get("error") or "Kronos is not installed. Run backend/scripts/install_kronos.sh."
        )

    key = _key(timeframe, max_pairs, pred_len)
    entry = KRONOS_SCAN_CACHE.get(key)
    running = key in _inflight and not _inflight[key].done()

    if entry is not None and entry.get("complete"):
        stale = time.time() - entry["ts"] >= cache_ttl(timeframe)
        if stale and not running:
            _start(timeframe, max_pairs, pred_len)  # stale-while-revalidate
        return _response(timeframe, pred_len, entry, warming=False, refreshing=stale or running)

    if not running:
        _start(timeframe, max_pairs, pred_len)
    return _response(timeframe, pred_len, KRONOS_SCAN_CACHE.get(key), warming=True, refreshing=False)
