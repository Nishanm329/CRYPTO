"""
Grid / DCA paper-trading bots.

Each bot is simulated against real Binance price action (no live orders, no keys).
On creation a bot is anchored to a recent kline window so it has an immediate,
honest paper-trading history; every refresh replays only the new bars since the
last processed candle and advances the bot's state.

Two strategies:

  * Grid  — places a ladder of buy levels across a price range. A level fills
            (paper buy) when price trades down through it, and the held inventory
            is sold one grid step higher for a realised profit. Profits in
            ranging markets; accumulates inventory in downtrends.

  * DCA   — opens a base order, then averages down with up to N safety orders as
            price falls by a fixed deviation, and closes the whole position
            (a "deal") for profit once price recovers take_profit_pct above the
            volume-weighted average entry, then re-opens a new deal.

Closed deals are fed into the verified track record (source="bot") so bot
performance is logged alongside the signal performance.

State persists to a JSON file so bots survive restarts.
"""
import json
import os
import time
import uuid
import asyncio
import threading
from datetime import datetime

import pandas as pd

from binance_client import get_klines

BOT_FILE = os.path.join(os.path.dirname(__file__), "bots.json")
SIM_BARS = 500              # bars of recent history to seed a new bot with
MAX_FILLS = 60              # most-recent fills retained per bot for display
EVAL_THROTTLE = 20          # seconds between live refreshes

_lock = threading.Lock()
_last_eval = 0.0

GRID_DEFAULTS = {"levels": 8, "order_size_usd": 100.0, "range_pct": 8.0}
DCA_DEFAULTS = {
    "base_order_usd": 100.0,
    "safety_order_usd": 100.0,
    "max_safety_orders": 5,
    "price_deviation_pct": 2.5,
    "take_profit_pct": 2.0,
}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def _load() -> list:
    if not os.path.exists(BOT_FILE):
        return []
    try:
        with open(BOT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save(bots: list) -> None:
    tmp = BOT_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(bots, f)
    os.replace(tmp, BOT_FILE)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------
async def create_bot(mode: str, symbol: str, timeframe: str, config: dict) -> dict:
    """Create and immediately seed a paper-trading bot over recent history."""
    mode = mode.lower()
    if mode not in ("grid", "dca"):
        raise ValueError("mode must be 'grid' or 'dca'")

    df = await get_klines(symbol, timeframe, SIM_BARS)
    if df.empty:
        raise ValueError(f"No market data for {symbol} {timeframe}")
    last_price = float(df["close"].iloc[-1])

    if mode == "grid":
        cfg = {**GRID_DEFAULTS, **{k: config[k] for k in GRID_DEFAULTS if k in config}}
        cfg["levels"] = max(2, min(50, int(cfg["levels"])))
        cfg["order_size_usd"] = max(1.0, float(cfg["order_size_usd"]))
        cfg["range_pct"] = max(1.0, min(60.0, float(cfg["range_pct"])))
        lower = last_price * (1 - cfg["range_pct"] / 100)
        upper = last_price * (1 + cfg["range_pct"] / 100)
        step = (upper - lower) / cfg["levels"]
        cfg["lower"] = round(lower, 8)
        cfg["upper"] = round(upper, 8)
        cfg["grid_prices"] = [round(lower + step * i, 8) for i in range(cfg["levels"] + 1)]
        cfg["step"] = round(step, 8)
        state = {"held": {}, "position_qty": 0.0, "position_cost": 0.0}
    else:
        cfg = {**DCA_DEFAULTS, **{k: config[k] for k in DCA_DEFAULTS if k in config}}
        cfg["base_order_usd"] = max(1.0, float(cfg["base_order_usd"]))
        cfg["safety_order_usd"] = max(1.0, float(cfg["safety_order_usd"]))
        cfg["max_safety_orders"] = max(0, min(20, int(cfg["max_safety_orders"])))
        cfg["price_deviation_pct"] = max(0.2, min(20.0, float(cfg["price_deviation_pct"])))
        cfg["take_profit_pct"] = max(0.2, min(20.0, float(cfg["take_profit_pct"])))
        state = {"deal": None}

    bot = {
        "id": uuid.uuid4().hex[:12],
        "name": config.get("name") or f"{mode.upper()} {symbol.replace('USDT', '')}",
        "mode": mode,
        "symbol": symbol,
        "timeframe": timeframe,
        "config": cfg,
        "state": state,
        "created_at": datetime.utcnow().isoformat(),
        "status": "running",
        "last_bar": None,
        "realized_pnl": 0.0,
        "completed_trades": 0,
        "fills": [],
        "closed_trades": [],
        "last_price": last_price,
    }
    await _step_bot(bot, df)
    with _lock:
        bots = _load()
        bots.append(bot)
        _save(bots)
    return _public(bot)


# ---------------------------------------------------------------------------
# Simulation step (replays bars after last_bar)
# ---------------------------------------------------------------------------
async def _step_bot(bot: dict, df: pd.DataFrame) -> None:
    if bot["status"] != "running":
        return
    last_bar = pd.to_datetime(bot["last_bar"]) if bot["last_bar"] else None
    bars = df[df.index > last_bar] if last_bar is not None else df
    if bars.empty:
        return

    from track_record import record_bot_trade

    if bot["mode"] == "grid":
        _step_grid(bot, bars)
    else:
        _step_dca(bot, bars)

    # flush any newly closed deals into the verified track record
    for ct in bot.get("_new_closed", []):
        record_bot_trade(bot, ct)
    bot.pop("_new_closed", None)

    bot["last_bar"] = bars.index[-1].isoformat()
    bot["last_price"] = float(bars["close"].iloc[-1])
    bot["fills"] = bot["fills"][-MAX_FILLS:]
    bot["closed_trades"] = bot["closed_trades"][-MAX_FILLS:]


def _step_grid(bot: dict, bars: pd.DataFrame) -> None:
    cfg = bot["config"]
    st = bot["state"]
    held = st["held"]  # key: str(level_index) -> {"price": buy_price, "qty": qty}
    step = cfg["step"]
    order_usd = cfg["order_size_usd"]
    new_closed = []

    for ts, row in zip(bars.index, bars.itertuples()):
        low, high = float(row.low), float(row.high)
        for i, lvl in enumerate(cfg["grid_prices"][:-1]):
            key = str(i)
            # Buy: price dips to an empty level
            if key not in held and low <= lvl:
                qty = order_usd / lvl
                held[key] = {"price": lvl, "qty": qty, "opened_at": ts.isoformat()}
                bot["fills"].append({
                    "time": ts.isoformat(), "side": "BUY",
                    "price": round(lvl, 8), "qty": round(qty, 8), "usd": round(order_usd, 2),
                })
            # Sell: a held level's target (one grid up) is reached
            if key in held:
                target = held[key]["price"] + step
                if high >= target:
                    pos = held.pop(key)
                    qty = pos["qty"]
                    pnl = (target - pos["price"]) * qty
                    bot["realized_pnl"] += pnl
                    bot["completed_trades"] += 1
                    bot["fills"].append({
                        "time": ts.isoformat(), "side": "SELL",
                        "price": round(target, 8), "qty": round(qty, 8),
                        "usd": round(target * qty, 2),
                    })
                    closed = {
                        "entry": round(pos["price"], 8), "exit": round(target, 8),
                        "qty": round(qty, 8), "pnl": round(pnl, 4),
                        "pnl_pct": round((target / pos["price"] - 1) * 100, 3),
                        "opened_at": pos["opened_at"], "closed_at": ts.isoformat(),
                    }
                    bot["closed_trades"].append(closed)
                    new_closed.append(closed)

    st["position_qty"] = round(sum(p["qty"] for p in held.values()), 8)
    st["position_cost"] = round(sum(p["qty"] * p["price"] for p in held.values()), 4)
    bot["_new_closed"] = new_closed


def _step_dca(bot: dict, bars: pd.DataFrame) -> None:
    cfg = bot["config"]
    st = bot["state"]
    tp = cfg["take_profit_pct"] / 100
    dev = cfg["price_deviation_pct"] / 100
    new_closed = []

    def _open_deal(price, ts):
        qty = cfg["base_order_usd"] / price
        deal = {
            "qty": qty, "cost": cfg["base_order_usd"], "avg": price,
            "safety_used": 0, "last_fill": price, "opened_at": ts.isoformat(),
        }
        bot["fills"].append({
            "time": ts.isoformat(), "side": "BUY", "price": round(price, 8),
            "qty": round(qty, 8), "usd": round(cfg["base_order_usd"], 2),
        })
        return deal

    for ts, row in zip(bars.index, bars.itertuples()):
        low, high, close = float(row.low), float(row.high), float(row.close)
        deal = st.get("deal")
        if deal is None:
            st["deal"] = deal = _open_deal(close, ts)

        # Safety orders as price drops a deviation below the last fill
        while deal["safety_used"] < cfg["max_safety_orders"]:
            trigger = deal["last_fill"] * (1 - dev)
            if low <= trigger:
                qty = cfg["safety_order_usd"] / trigger
                deal["qty"] += qty
                deal["cost"] += cfg["safety_order_usd"]
                deal["avg"] = deal["cost"] / deal["qty"]
                deal["last_fill"] = trigger
                deal["safety_used"] += 1
                bot["fills"].append({
                    "time": ts.isoformat(), "side": "BUY", "price": round(trigger, 8),
                    "qty": round(qty, 8), "usd": round(cfg["safety_order_usd"], 2),
                })
            else:
                break

        # Take profit on the whole deal
        target = deal["avg"] * (1 + tp)
        if high >= target:
            pnl = (target - deal["avg"]) * deal["qty"]
            bot["realized_pnl"] += pnl
            bot["completed_trades"] += 1
            bot["fills"].append({
                "time": ts.isoformat(), "side": "SELL", "price": round(target, 8),
                "qty": round(deal["qty"], 8), "usd": round(target * deal["qty"], 2),
            })
            closed = {
                "entry": round(deal["avg"], 8), "exit": round(target, 8),
                "qty": round(deal["qty"], 8), "pnl": round(pnl, 4),
                "pnl_pct": round(tp * 100, 3),
                "safety_used": deal["safety_used"],
                "opened_at": deal["opened_at"], "closed_at": ts.isoformat(),
            }
            bot["closed_trades"].append(closed)
            new_closed.append(closed)
            st["deal"] = _open_deal(close, ts)

    deal = st.get("deal")
    st["position_qty"] = round(deal["qty"], 8) if deal else 0.0
    st["position_cost"] = round(deal["cost"], 4) if deal else 0.0
    st["avg_entry"] = round(deal["avg"], 8) if deal else None
    st["safety_used"] = deal["safety_used"] if deal else 0
    bot["_new_closed"] = new_closed


# ---------------------------------------------------------------------------
# Refresh + public views
# ---------------------------------------------------------------------------
def _unrealized(bot: dict) -> float:
    st = bot["state"]
    qty = st.get("position_qty", 0.0)
    cost = st.get("position_cost", 0.0)
    if qty <= 0:
        return 0.0
    return round(bot["last_price"] * qty - cost, 4)


def _public(bot: dict) -> dict:
    st = bot["state"]
    return {
        "id": bot["id"],
        "name": bot["name"],
        "mode": bot["mode"],
        "symbol": bot["symbol"],
        "timeframe": bot["timeframe"],
        "status": bot["status"],
        "created_at": bot["created_at"],
        "config": bot["config"],
        "last_price": round(bot["last_price"], 8),
        "realized_pnl": round(bot["realized_pnl"], 2),
        "unrealized_pnl": _unrealized(bot),
        "completed_trades": bot["completed_trades"],
        "position_qty": st.get("position_qty", 0.0),
        "position_cost": round(st.get("position_cost", 0.0), 2),
        "avg_entry": st.get("avg_entry"),
        "safety_used": st.get("safety_used"),
        "open_levels": len(st.get("held", {})) if bot["mode"] == "grid" else None,
        "fills": list(reversed(bot["fills"][-25:])),
        "closed_trades": list(reversed(bot["closed_trades"][-25:])),
    }


async def refresh_all() -> None:
    """Replay new bars for every running bot. Throttled."""
    global _last_eval
    if (time.time() - _last_eval) < EVAL_THROTTLE:
        return
    _last_eval = time.time()

    with _lock:
        bots = _load()
    running = [b for b in bots if b["status"] == "running"]
    if not running:
        return

    sem = asyncio.Semaphore(6)

    async def _refresh(bot):
        async with sem:
            try:
                df = await get_klines(bot["symbol"], bot["timeframe"], SIM_BARS)
                await _step_bot(bot, df)
            except Exception:
                return

    await asyncio.gather(*[_refresh(b) for b in running])
    with _lock:
        _save(bots)


async def list_bots() -> list:
    await refresh_all()
    with _lock:
        bots = _load()
    return [_public(b) for b in bots]


def stop_bot(bot_id: str) -> bool:
    with _lock:
        bots = _load()
        for b in bots:
            if b["id"] == bot_id:
                b["status"] = "stopped"
                _save(bots)
                return True
    return False


def start_bot(bot_id: str) -> bool:
    with _lock:
        bots = _load()
        for b in bots:
            if b["id"] == bot_id:
                b["status"] = "running"
                _save(bots)
                return True
    return False


def delete_bot(bot_id: str) -> bool:
    with _lock:
        bots = _load()
        new = [b for b in bots if b["id"] != bot_id]
        if len(new) == len(bots):
            return False
        _save(new)
    return True


def get_summary() -> dict:
    with _lock:
        bots = _load()
    realized = round(sum(b["realized_pnl"] for b in bots), 2)
    unrealized = round(sum(_unrealized(b) for b in bots), 2)
    trades = sum(b["completed_trades"] for b in bots)
    return {
        "bots": len(bots),
        "running": sum(1 for b in bots if b["status"] == "running"),
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_pnl": round(realized + unrealized, 2),
        "completed_trades": trades,
    }
