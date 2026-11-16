"""
Tests for the optional Kronos forecaster. A fake predictor stands in for the
real model so these run without PyTorch or downloaded weights.
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import AsyncMock, patch

import kronos_forecaster


def _klines(n=200, start="2026-01-01", freq="1h"):
    idx = pd.date_range(start, periods=n, freq=freq)
    close = 100 + np.cumsum(np.random.default_rng(0).normal(0, 1, n))
    df = pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000.0,
            "quote_volume": 100000.0,
        },
        index=idx,
    )
    df.index.name = "timestamp"
    return df


class FakePredictor:
    device = "cpu"

    def __init__(self):
        self.calls = []

    def predict(self, df, x_timestamp, y_timestamp, pred_len, **kw):
        self.calls.append({"df": df, "x": x_timestamp, "y": y_timestamp, "pred_len": pred_len, **kw})
        last = float(df["close"].iloc[-1])
        closes = last * (1 + 0.01 * np.arange(1, pred_len + 1))
        return pd.DataFrame(
            {
                "open": closes - 0.5,
                "high": closes - 1.0,  # deliberately invalid wick, should be fixed
                "low": closes + 1.0,   # deliberately invalid wick, should be fixed
                "close": closes,
                "volume": -5.0,
                "amount": 0.0,
            },
            index=pd.DatetimeIndex(y_timestamp),
        )


@pytest.fixture
def fake_predictor(monkeypatch):
    fake = FakePredictor()
    monkeypatch.setattr(kronos_forecaster, "_predictor", fake)
    return fake


def test_forecast_builds_future_timestamps_and_valid_candles(fake_predictor):
    df = _klines(200)
    pred = kronos_forecaster.forecast(df, "1h", pred_len=12, seed=None)

    assert len(pred) == 12
    assert pred.index[0] == df.index[-1] + pd.Timedelta(hours=1)
    assert pred.index[-1] == df.index[-1] + pd.Timedelta(hours=12)
    assert (pred["high"] >= pred[["open", "close"]].max(axis=1)).all()
    assert (pred["low"] <= pred[["open", "close"]].min(axis=1)).all()
    assert (pred["volume"] >= 0).all()

    call = fake_predictor.calls[0]
    assert list(call["df"].columns) == ["open", "high", "low", "close", "volume", "amount"]
    assert len(call["x"]) == 200 and len(call["y"]) == 12


def test_forecast_truncates_to_max_context_and_caps_pred_len(fake_predictor):
    df = _klines(kronos_forecaster.MAX_CONTEXT + 100)
    pred = kronos_forecaster.forecast(df, "1h", pred_len=10_000, seed=None)
    assert len(pred) == kronos_forecaster.MAX_PRED_LEN
    assert len(fake_predictor.calls[0]["df"]) == kronos_forecaster.MAX_CONTEXT


def test_forecast_rejects_short_history(fake_predictor):
    with pytest.raises(ValueError):
        kronos_forecaster.forecast(_klines(10), "1h", seed=None)


def test_unknown_timeframe():
    with pytest.raises(ValueError):
        kronos_forecaster.interval_delta("7h")


def test_summarize_direction():
    pred = pd.DataFrame({"open": [100, 101], "high": [102, 103], "low": [99, 100], "close": [101, 103]})
    s = kronos_forecaster.summarize(100.0, pred)
    assert s["direction"] == "UP"
    assert s["change_pct"] == pytest.approx(3.0)
    assert s["pred_high"] == 103 and s["pred_low"] == 99


AUTH = {"Authorization": "Bearer demo-key-public"}


def test_kronos_endpoint_returns_forecast(client, fake_predictor):
    import main

    main._response_cache.clear()
    with patch("main.get_klines", new=AsyncMock(return_value=_klines(300))):
        r = client.get("/api/kronos/btc?timeframe=1h&pred_len=6", headers=AUTH)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["symbol"] == "BTCUSDT"
    assert len(data["forecast"]) == 6
    assert data["summary"]["direction"] == "UP"
    assert data["forecast"][0]["time"] > 0


def test_kronos_endpoint_501_when_not_installed(client, monkeypatch):
    import main

    main._response_cache.clear()

    def boom(*a, **k):
        raise kronos_forecaster.KronosUnavailable("Kronos is not installed")

    monkeypatch.setattr(kronos_forecaster, "_load_predictor", boom)
    with patch("main.get_klines", new=AsyncMock(return_value=_klines(300))):
        r = client.get("/api/kronos/ETHUSDT?timeframe=4h", headers=AUTH)
    assert r.status_code == 501
    assert "not installed" in r.json()["detail"]


def test_kronos_endpoint_rejects_bad_timeframe(client):
    r = client.get("/api/kronos/BTCUSDT?timeframe=7h", headers=AUTH)
    assert r.status_code == 400
