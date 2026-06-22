"""
Verified track record — a forward-tested performance log of the signals the
engine actually publishes.

Every published signal (confidence above the publish threshold) is recorded at
emit time with its entry, stop and take-profit levels. Open records are later
forward-evaluated against real price action to a resolved win/loss outcome, so
the aggregate stats (win rate, avg R, profit factor, equity curve) are an
honest, reproducible record rather than a marketing claim.

Storage is a JSON-lines file so the lightweight, DB-free service stays simple
and the history survives restarts.
"""
import json
import os
import time
import uuid
import asyncio
import threading
from datetime import datetime

import pandas as pd

from binance_client import get_klines, get_top_volume_pairs
from indicators import add_all_indicators, calculate_volume_profile
from signals import calculate_risk_levels, calculate_confidence

TRACK_FILE = os.path.join(os.path.dirname(__file__), "signal_track.jsonl")
PUBLISH_THRESHOLD = 60       # only signals at/above this confidence are tracked
MAX_OPEN_BARS = 200          # bars after entry before an unresolved signal expires
SEED_TIMEFRAMES = ["4h", "1d"]
SEED_SYMBOLS = 12
SEED_BARS = 1000

_lock = threading.Lock()
_last_eval = 0.0
_seeded = False


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------
def _load() -> list:
    if not os.path.exists(TRACK_FILE):
        return []
    out = []
    with open(TRACK_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out


def _save(records: list) -> None:
    tmp = TRACK_FILE + ".tmp"
    with open(tmp, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    os.replace(tmp, TRACK_FILE)


# ---------------------------------------------------------------------------
# Outcome evaluation
# ---------------------------------------------------------------------------
def _evaluate_outcome(direction, entry, sl, tp1, tp2, tp3, highs, lows):
    """Walk forward candle by candle. Returns (status, result_R, exit_reason).

    Conservative: if a candle touches both stop and a target, the stop counts
    first. Best take-profit reached before the stop sets the realised R.
    """
    is_long = direction == "LONG"
    max_r = 0.0
    reason = None
    for h, l in zip(highs, lows):
        if is_long:
            sl_hit = l <= sl
            if sl_hit and max_r == 0:
                return "loss", -1.0, "STOP_LOSS"
            if h >= tp3:
                return "win", 3.0, "TP3"
            if h >= tp2:
                max_r, reason = 2.0, "TP2"
            elif h >= tp1 and max_r < 1.0:
                max_r, reason = 1.0, "TP1"
            if sl_hit and max_r > 0:
                return "win", max_r, reason
        else:
            sl_hit = h >= sl
            if sl_hit and max_r == 0:
                return "loss", -1.0, "STOP_LOSS"
            if l <= tp3:
                return "win", 3.0, "TP3"
            if l <= tp2:
                max_r, reason = 2.0, "TP2"
            elif l <= tp1 and max_r < 1.0:
                max_r, reason = 1.0, "TP1"
            if sl_hit and max_r > 0:
                return "win", max_r, reason
    if max_r > 0:
        return "open", max_r, reason  # unrealised best; not yet stopped or expired
    return "open", 0.0, None


# ---------------------------------------------------------------------------
# Recording (called from the scanner when a signal is published)
# ---------------------------------------------------------------------------
def record_signal(signal) -> None:
    """Append a published signal as an open tracked record (deduplicated)."""
    try:
        if signal is None or signal.confidence < PUBLISH_THRESHOLD:
            return
        tps = {tp.level: tp.price for tp in signal.take_profits}
        with _lock:
            records = _load()
            for r in records:
                if (
                    r["status"] == "open"
                    and r["symbol"] == signal.symbol
                    and r["timeframe"] == signal.timeframe
                    and r["direction"] == signal.direction.value
                ):
                    return  # an identical open setup is already tracked
            records.append({
                "id": uuid.uuid4().hex[:12],
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "direction": signal.direction.value,
                "entry": float(signal.entry_price),
                "stop_loss": float(signal.stop_loss),
                "tp1": float(tps.get(1)),
                "tp2": float(tps.get(2)),
                "tp3": float(tps.get(3)),
                "confidence": int(signal.confidence),
                "ai_probability": float(signal.ai_probability),
                "created_at": signal.timestamp,
                "status": "open",
                "result_r": None,
                "exit_reason": None,
                "closed_at": None,
                "source": "live",
            })
            _save(records)
    except Exception:
        return


def record_bot_trade(bot, closed) -> None:
    """Log a closed paper-trading bot deal into the verified track record.

    Bot deals close in profit (a grid step or DCA take-profit), so their R is
    expressed relative to the bot's own profit step: 1R == one realised target.
    Records are tagged source="bot" so the UI can distinguish them from signals.
    """
    try:
        cfg = bot.get("config", {})
        if bot["mode"] == "grid":
            step_pct = (cfg.get("step", 0) / closed["entry"] * 100) if closed.get("entry") else 0
        else:
            step_pct = cfg.get("take_profit_pct", 0)
        result_r = round(closed["pnl_pct"] / step_pct, 3) if step_pct else 0.0
        with _lock:
            records = _load()
            records.append({
                "id": uuid.uuid4().hex[:12],
                "symbol": bot["symbol"],
                "timeframe": bot["timeframe"],
                "direction": "LONG",
                "entry": closed["entry"],
                "stop_loss": None,
                "tp1": closed["exit"],
                "tp2": None,
                "tp3": None,
                "confidence": None,
                "ai_probability": None,
                "created_at": closed["opened_at"],
                "status": "win" if closed["pnl"] >= 0 else "loss",
                "result_r": result_r,
                "exit_reason": f"{bot['mode'].upper()}_TP",
                "closed_at": closed["closed_at"],
                "source": "bot",
            })
            _save(records)
    except Exception:
        return


# ---------------------------------------------------------------------------
# Forward-evaluation of open records
# ---------------------------------------------------------------------------
async def evaluate_open(force: bool = False) -> None:
    """Resolve open records against fresh price action. Throttled to 30s."""
    global _last_eval
    if not force and (time.time() - _last_eval) < 30:
        return
    _last_eval = time.time()

    with _lock:
        records = _load()
    open_recs = [r for r in records if r["status"] == "open"]
    if not open_recs:
        return

    sem = asyncio.Semaphore(8)

    async def _resolve(rec):
        async with sem:
            try:
                df = await get_klines(rec["symbol"], rec["timeframe"], 1000)
            except Exception:
                return
            created = pd.to_datetime(rec["created_at"])
            after = df[df.index > created]
            if after.empty:
                return
            highs = after["high"].tolist()
            lows = after["low"].tolist()
            status, r_val, reason = _evaluate_outcome(
                rec["direction"], rec["entry"], rec["stop_loss"],
                rec["tp1"], rec["tp2"], rec["tp3"], highs, lows,
            )
            if status in ("win", "loss"):
                rec["status"] = status
                rec["result_r"] = round(r_val, 3)
                rec["exit_reason"] = reason
                rec["closed_at"] = after.index[-1].isoformat()
            elif len(after) >= MAX_OPEN_BARS:
                rec["status"] = "expired"
                rec["exit_reason"] = "EXPIRED"
                rec["closed_at"] = after.index[-1].isoformat()

    await asyncio.gather(*[_resolve(r) for r in open_recs])
    with _lock:
        _save(records)


# ---------------------------------------------------------------------------
# One-time historical seed so the record is populated immediately
# ---------------------------------------------------------------------------
async def seed_if_empty() -> None:
    """Forward-test the live signal logic over recent history once, so the
    track record is immediately populated with resolved outcomes on real data."""
    global _seeded
    if _seeded:
        return
    with _lock:
        existing = _load()
        if any(r.get("source") == "seed" for r in existing):
            _seeded = True
            return
    _seeded = True

    try:
        symbols = await get_top_volume_pairs(SEED_SYMBOLS)
    except Exception:
        return

    seeded: list = []
    sem = asyncio.Semaphore(6)

    async def _seed_one(symbol, tf):
        async with sem:
            try:
                df = await get_klines(symbol, tf, SEED_BARS)
            except Exception:
                return
            if len(df) < 220:
                return
            d = add_all_indicators(df)
            ema7 = d["ema7"].values
            ema25 = d["ema25"].values
            highs = d["high"].values
            lows = d["low"].values
            closes = d["close"].values
            idx = d.index
            for i in range(210, len(d) - 1):
                if pd.isna(ema7[i]) or pd.isna(ema25[i]) or pd.isna(ema7[i - 1]):
                    continue
                up = ema7[i - 1] <= ema25[i - 1] and ema7[i] > ema25[i]
                down = ema7[i - 1] >= ema25[i - 1] and ema7[i] < ema25[i]
                if not (up or down):
                    continue
                direction = "LONG" if up else "SHORT"
                slice_df = d.iloc[: i + 1]
                entry = float(closes[i])
                try:
                    sl, tp1, tp2, tp3 = calculate_risk_levels(slice_df, direction, entry)
                    vp = calculate_volume_profile(slice_df)
                    conf = calculate_confidence(slice_df, direction, [], vol_profile=vp)
                except Exception:
                    continue
                if conf < PUBLISH_THRESHOLD or abs(entry - sl) == 0:
                    continue
                status, r_val, reason = _evaluate_outcome(
                    direction, entry, sl, tp1, tp2, tp3,
                    highs[i + 1:].tolist(), lows[i + 1:].tolist(),
                )
                rec = {
                    "id": uuid.uuid4().hex[:12],
                    "symbol": symbol,
                    "timeframe": tf,
                    "direction": direction,
                    "entry": round(entry, 6),
                    "stop_loss": round(float(sl), 6),
                    "tp1": round(float(tp1), 6),
                    "tp2": round(float(tp2), 6),
                    "tp3": round(float(tp3), 6),
                    "confidence": int(conf),
                    "ai_probability": None,
                    "created_at": idx[i].isoformat(),
                    "status": status if status in ("win", "loss") else "expired",
                    "result_r": round(r_val, 3) if status in ("win", "loss") else None,
                    "exit_reason": reason if status in ("win", "loss") else "EXPIRED",
                    "closed_at": idx[-1].isoformat(),
                    "source": "seed",
                }
                seeded.append(rec)

    tasks = [_seed_one(s, tf) for s in symbols for tf in SEED_TIMEFRAMES]
    await asyncio.gather(*tasks)

    if seeded:
        seeded.sort(key=lambda r: r["created_at"])
        with _lock:
            existing = _load()
            _save(existing + seeded)


# ---------------------------------------------------------------------------
# Aggregate stats
# ---------------------------------------------------------------------------
def get_stats() -> dict:
    records = _load()
    closed = [r for r in records if r["status"] in ("win", "loss")]
    open_recs = [r for r in records if r["status"] == "open"]
    expired = [r for r in records if r["status"] == "expired"]

    wins = [r for r in closed if r["status"] == "win"]
    losses = [r for r in closed if r["status"] == "loss"]
    n = len(closed)
    win_rate = round(len(wins) / n * 100, 1) if n else 0.0

    rs = [r["result_r"] for r in closed if r.get("result_r") is not None]
    total_r = round(sum(rs), 2)
    avg_r = round(sum(rs) / len(rs), 3) if rs else 0.0
    gross_win = sum(x for x in rs if x > 0)
    gross_loss = abs(sum(x for x in rs if x < 0))
    profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (
        round(gross_win, 2) if gross_win > 0 else 0.0
    )

    # Equity curve in R, ordered by close time
    closed_sorted = sorted(closed, key=lambda r: r.get("closed_at") or "")
    equity, cum = [], 0.0
    for r in closed_sorted:
        cum += r.get("result_r") or 0.0
        equity.append(round(cum, 2))
    peak, max_dd = 0.0, 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)

    # Breakdown by timeframe and direction
    def _bucket(key):
        out = {}
        for r in closed:
            k = r[key]
            b = out.setdefault(k, {"trades": 0, "wins": 0, "r": 0.0})
            b["trades"] += 1
            b["wins"] += 1 if r["status"] == "win" else 0
            b["r"] += r.get("result_r") or 0.0
        return [
            {
                "key": k,
                "trades": b["trades"],
                "win_rate": round(b["wins"] / b["trades"] * 100, 1),
                "total_r": round(b["r"], 2),
            }
            for k, b in sorted(out.items(), key=lambda kv: kv[1]["trades"], reverse=True)
        ]

    recent = sorted(closed, key=lambda r: r.get("closed_at") or "", reverse=True)[:25]

    return {
        "total_signals": len(records),
        "closed": n,
        "open": len(open_recs),
        "expired": len(expired),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "avg_r": avg_r,
        "total_r": total_r,
        "profit_factor": profit_factor,
        "max_drawdown_r": round(max_dd, 2),
        "best_r": round(max(rs), 2) if rs else 0.0,
        "worst_r": round(min(rs), 2) if rs else 0.0,
        "equity_curve": equity,
        "by_timeframe": _bucket("timeframe"),
        "by_direction": _bucket("direction"),
        "recent_trades": [
            {
                "symbol": r["symbol"],
                "timeframe": r["timeframe"],
                "direction": r["direction"],
                "confidence": r["confidence"],
                "entry": r["entry"],
                "result_r": r.get("result_r"),
                "exit_reason": r.get("exit_reason"),
                "status": r["status"],
                "created_at": r["created_at"],
                "closed_at": r.get("closed_at"),
                "source": r.get("source", "live"),
            }
            for r in recent
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }
