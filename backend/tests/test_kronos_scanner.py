"""
Tests for the Kronos scanner mode. A fake predictor stands in for the model,
and Binance calls are patched, so these run without PyTorch or network access.
"""
import asyncio
import time
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

import kronos_forecaster
import kronos_scanner
import scanner
from models import ScanResult, SignalDirection

AUTH = {"Authorization": "Bearer demo-key-public"}
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
# Per-symbol drift per predicted candle: BTC up, ETH down, SOL flat.
DRIFT = {"BTCUSDT": 0.002, "ETHUSDT": -0.004, "SOLUSDT": 0.0}


def _klines(symbol, n=400):
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    close = 100 + np.cumsum(np.random.default_rng(1).normal(0, 0.5, n))
    df = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close,
         "volume": 1000.0, "quote_volume": 1e5},
        index=idx,
    )
    df.attrs["symbol"] = symbol
    return df


class FakePredictor:
    device = "cpu"
    current = None  # symbol of the most recent get_klines call

    def predict(self, df, x_timestamp, y_timestamp, pred_len, **kw):
        last = float(df["close"].iloc[-1])
        drift = DRIFT[self.current]
        closes = last * (1 + drift * np.arange(1, pred_len + 1))
        return pd.DataFrame(
            {"open": closes, "high": closes * 1.001, "low": closes * 0.999,
             "close": closes, "volume": 10.0},
            index=pd.DatetimeIndex(y_timestamp),
        )


@pytest.fixture
def env(monkeypatch):
    fake = FakePredictor()
    monkeypatch.setattr(kronos_forecaster, "_predictor", fake)
    kronos_scanner.KRONOS_SCAN_CACHE.clear()
    kronos_scanner._inflight.clear()
    scanner.SCAN_CACHE.clear()

    async def fake_klines(symbol, tf, limit=300):
        fake.current = symbol
        return _klines(symbol)

    tickers = {s: {"lastPrice": "100", "priceChangePercent": "1.5", "quoteVolume": "1e6"} for s in PAIRS}
    patches = [
        patch("kronos_scanner.get_top_volume_pairs", new=AsyncMock(return_value=PAIRS)),
        patch("kronos_scanner.batch_get_tickers", new=AsyncMock(return_value=tickers)),
        patch("kronos_scanner.get_klines", new=fake_klines),
    ]
    for p in patches:
        p.start()
    yield fake
    for p in patches:
        p.stop()
    scanner.SCAN_CACHE.clear()


def _ema(symbol, direction, conf=70):
    return ScanResult(symbol=symbol, timeframe="1h", direction=direction, confidence=conf,
                      ai_probability=0.6, price=100, change_24h=0, volume_24h=0,
                      rr_ratio=2, timestamp="2026-01-01T00:00:00")


async def _scan_to_completion():
    first = await kronos_scanner.scan_kronos("1h", 3, 12)
    for _ in range(200):
        task = kronos_scanner._inflight.get("1h_3_12")
        if task is None:
            break
        await asyncio.sleep(0.01)
    return first, await kronos_scanner.scan_kronos("1h", 3, 12)


def test_scan_warms_then_ranks_by_predicted_move(env):
    scanner.SCAN_CACHE["1h_100"] = {
        "ts": time.time(),
        "results": [_ema("BTCUSDT", SignalDirection.LONG), _ema("ETHUSDT", SignalDirection.LONG)],
    }
    first, done = asyncio.run(_scan_to_completion())

    assert first["warming"] is True
    assert done["warming"] is False
    assert done["progress"] == {"done": 3, "total": 3}
    syms = [r["symbol"] for r in done["results"]]
    # ETH has the biggest absolute move, then BTC, then flat SOL.
    assert syms == ["ETHUSDT", "BTCUSDT", "SOLUSDT"]
    by = {r["symbol"]: r for r in done["results"]}
    assert by["BTCUSDT"]["direction"] == "UP" and by["BTCUSDT"]["agrees_with_ema"] is True
    assert by["ETHUSDT"]["direction"] == "DOWN" and by["ETHUSDT"]["agrees_with_ema"] is False
    assert by["SOLUSDT"]["direction"] == "FLAT" and by["SOLUSDT"]["agrees_with_ema"] is None
    assert by["BTCUSDT"]["ema_confidence"] == 70
    assert (done["up_count"], done["down_count"], done["flat_count"]) == (1, 1, 1)


def test_completed_scan_is_served_from_cache(env):
    async def run():
        await _scan_to_completion()
        again = await kronos_scanner.scan_kronos("1h", 3, 12)
        return again, "1h_3_12" in kronos_scanner._inflight

    again, restarted = asyncio.run(run())
    assert again["warming"] is False and again["refreshing"] is False
    assert not restarted


def test_one_failing_pair_does_not_sink_the_scan(env):
    original = kronos_scanner.get_klines

    async def flaky(symbol, tf, limit=300):
        if symbol == "SOLUSDT":
            raise RuntimeError("binance hiccup")
        return await original(symbol, tf, limit)

    with patch("kronos_scanner.get_klines", new=flaky):
        _, done = asyncio.run(_scan_to_completion())
    assert done["errors"] == 1
    assert {r["symbol"] for r in done["results"]} == {"BTCUSDT", "ETHUSDT"}


def test_unavailable_raises(monkeypatch):
    monkeypatch.setattr(kronos_forecaster, "status", lambda: {"available": False, "error": None})
    with pytest.raises(kronos_forecaster.KronosUnavailable):
        asyncio.run(kronos_scanner.scan_kronos("1h", 5, 12))


def test_endpoint_501_when_not_installed(client, monkeypatch):
    monkeypatch.setattr(kronos_forecaster, "status", lambda: {"available": False, "error": "Kronos is not installed"})
    r = client.get("/api/scan/kronos?timeframe=1h", headers=AUTH)
    assert r.status_code == 501
    assert "not installed" in r.json()["detail"]


def test_endpoint_rejects_bad_timeframe(client):
    r = client.get("/api/scan/kronos?timeframe=7h", headers=AUTH)
    assert r.status_code == 400


def test_endpoint_returns_warming_response(client, env):
    r = client.get("/api/scan/kronos?timeframe=1h&max_pairs=5&pred_len=12", headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True and body["warming"] is True
    assert body["model"] == kronos_forecaster.MODEL_NAME
