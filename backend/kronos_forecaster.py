"""
Kronos candlestick forecasting.

Kronos (https://github.com/shiyu-coder/Kronos, MIT) is a foundation model
pre-trained on K-line (OHLCV) data from 45+ exchanges. Given recent candles it
autoregressively generates the next N candles.

Kronos is an OPTIONAL dependency: it needs PyTorch and the model code from the
Kronos repo, which are too heavy for the free-tier deploy. Install with:

    ./scripts/install_kronos.sh

Until then the /api/kronos endpoint returns 503 and the rest of the API is
unaffected.

Env vars:
    KRONOS_REPO_PATH   path to a checkout of shiyu-coder/Kronos
                       (default: backend/vendor/Kronos)
    KRONOS_MODEL       NeoQuasar/Kronos-mini | Kronos-small (default) | Kronos-base
    KRONOS_TOKENIZER   override tokenizer (auto-picked to match the model)
    KRONOS_DEVICE      cpu | cuda:0 | mps (default: auto-detect)
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO_PATH = os.path.join(_BACKEND_DIR, "vendor", "Kronos")

MODEL_NAME = os.getenv("KRONOS_MODEL", "NeoQuasar/Kronos-small")
# Kronos-mini pairs with the 2k tokenizer and a 2048 context; small/base use 512.
_IS_MINI = MODEL_NAME.lower().endswith("kronos-mini")
TOKENIZER_NAME = os.getenv(
    "KRONOS_TOKENIZER",
    "NeoQuasar/Kronos-Tokenizer-2k" if _IS_MINI else "NeoQuasar/Kronos-Tokenizer-base",
)
MAX_CONTEXT = 2048 if _IS_MINI else 512

MAX_PRED_LEN = 120
MAX_SAMPLES = 5

_INTERVAL_DELTAS = {
    "1m": pd.Timedelta(minutes=1),
    "3m": pd.Timedelta(minutes=3),
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "2h": pd.Timedelta(hours=2),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
    "3d": pd.Timedelta(days=3),
    "1w": pd.Timedelta(weeks=1),
}


class KronosUnavailable(RuntimeError):
    """Raised when the optional Kronos dependencies are not installed."""


_predictor = None
_load_error: Optional[str] = None
_load_lock = threading.Lock()
# One inference at a time: the model is CPU/GPU-bound and not re-entrant.
_infer_lock = threading.Lock()


def interval_delta(timeframe: str) -> pd.Timedelta:
    if timeframe not in _INTERVAL_DELTAS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return _INTERVAL_DELTAS[timeframe]


def _load_predictor():
    """Import Kronos and load weights from the Hugging Face Hub (once)."""
    global _predictor, _load_error
    if _predictor is not None:
        return _predictor
    with _load_lock:
        if _predictor is not None:
            return _predictor
        repo_path = os.getenv("KRONOS_REPO_PATH", DEFAULT_REPO_PATH)
        if os.path.isdir(repo_path) and repo_path not in sys.path:
            # The Kronos repo exposes its code as a top-level `model` package.
            sys.path.append(repo_path)
        try:
            from model import Kronos, KronosPredictor, KronosTokenizer  # type: ignore
        except ImportError as e:
            _load_error = (
                f"Kronos is not installed ({e}). Run backend/scripts/install_kronos.sh "
                "or set KRONOS_REPO_PATH to a checkout of github.com/shiyu-coder/Kronos."
            )
            raise KronosUnavailable(_load_error) from e

        logger.info("Loading Kronos model=%s tokenizer=%s", MODEL_NAME, TOKENIZER_NAME)
        started = time.time()
        tokenizer = KronosTokenizer.from_pretrained(TOKENIZER_NAME)
        model = Kronos.from_pretrained(MODEL_NAME)
        _predictor = KronosPredictor(
            model, tokenizer, device=os.getenv("KRONOS_DEVICE") or None, max_context=MAX_CONTEXT
        )
        logger.info("Kronos loaded in %.1fs on %s", time.time() - started, _predictor.device)
        return _predictor


def status() -> dict:
    """Cheap availability check that does not load model weights."""
    available = _predictor is not None
    if not available:
        repo_path = os.getenv("KRONOS_REPO_PATH", DEFAULT_REPO_PATH)
        try:
            import torch  # noqa: F401
            available = os.path.isdir(os.path.join(repo_path, "model"))
        except ImportError:
            available = False
    return {
        "available": available,
        "loaded": _predictor is not None,
        "model": MODEL_NAME,
        "tokenizer": TOKENIZER_NAME,
        "max_context": MAX_CONTEXT,
        "error": _load_error,
    }


def forecast(
    df: pd.DataFrame,
    timeframe: str,
    pred_len: int = 24,
    sample_count: int = 1,
    temperature: float = 1.0,
    top_p: float = 0.9,
    seed: Optional[int] = 42,
) -> pd.DataFrame:
    """
    Forecast the next `pred_len` candles.

    `df` is the Binance klines frame from binance_client.get_klines (timestamp
    index, open/high/low/close/volume[/quote_volume] columns). Returns a frame of
    predicted open/high/low/close/volume indexed by future timestamps.
    Blocking: call via asyncio.to_thread from async code.
    """
    pred_len = max(1, min(int(pred_len), MAX_PRED_LEN))
    sample_count = max(1, min(int(sample_count), MAX_SAMPLES))
    step = interval_delta(timeframe)

    hist = df.tail(MAX_CONTEXT)
    if len(hist) < 32:
        raise ValueError(f"Need at least 32 candles for a forecast, got {len(hist)}")

    x_df = hist[["open", "high", "low", "close", "volume"]].copy()
    # Kronos' "amount" is turnover; Binance gives it as quote volume.
    if "quote_volume" in hist.columns:
        x_df["amount"] = hist["quote_volume"].values
    x_df = x_df.reset_index(drop=True)

    x_timestamp = pd.Series(pd.DatetimeIndex(hist.index))
    last_ts = hist.index[-1]
    y_index = pd.DatetimeIndex([last_ts + step * (i + 1) for i in range(pred_len)])
    y_timestamp = pd.Series(y_index)

    predictor = _load_predictor()
    with _infer_lock:
        if seed is not None:
            # Fixed seed so repeat requests for the same candles agree.
            try:
                import torch

                torch.manual_seed(seed)
            except ImportError:
                pass
        pred = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=pred_len,
            T=temperature,
            top_p=top_p,
            sample_count=sample_count,
            verbose=False,
        )

    pred = pred[["open", "high", "low", "close", "volume"]].copy()
    pred.index = y_index
    # Sampling can produce slightly inconsistent wicks; keep candles valid.
    body_hi = pred[["open", "close"]].max(axis=1)
    body_lo = pred[["open", "close"]].min(axis=1)
    pred["high"] = pred["high"].where(pred["high"] >= body_hi, body_hi)
    pred["low"] = pred["low"].where(pred["low"] <= body_lo, body_lo)
    pred["volume"] = pred["volume"].clip(lower=0)
    return pred


def summarize(last_close: float, pred: pd.DataFrame) -> dict:
    """Headline numbers for the UI: where Kronos thinks price ends up."""
    pred_close = float(pred["close"].iloc[-1])
    change_pct = (pred_close / last_close - 1) * 100 if last_close else 0.0
    if change_pct > 0.5:
        direction = "UP"
    elif change_pct < -0.5:
        direction = "DOWN"
    else:
        direction = "FLAT"
    return {
        "last_close": last_close,
        "pred_close": pred_close,
        "change_pct": round(change_pct, 3),
        "direction": direction,
        "pred_high": float(pred["high"].max()),
        "pred_low": float(pred["low"].min()),
    }
