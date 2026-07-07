"""
Grid / DCA / Signal paper-trading bots.

Each bot is simulated against real Binance price action (no live orders, no keys).
On creation a bot is anchored to a recent kline window so it has an immediate,
honest paper-trading history; every refresh replays only the new bars since the
last processed candle and advances the bot's state.

Three strategies:

  * Grid   — places a ladder of buy levels across a price range. A level fills
             (paper buy) when price trades down through it, and the held inventory
             is sold one grid step higher for a realised profit. Profits in
             ranging markets; accumulates inventory in downtrends.

  * DCA    — opens a base order, then averages down with up to N safety orders as
             price falls by a fixed deviation, and closes the whole position
             (a "deal") for profit once price recovers take_profit_pct above the
             volume-weighted average entry, then re-opens a new deal. A stop-loss
             cuts the deal for a loss once safety orders are exhausted and price
             keeps falling, instead of averaging down forever.

  * Signal — trades the app's own EMA7/25 + confidence-scored signals
             (signals.generate_signal). A signal detected on a closed candle is
             executed at the NEXT candle's open (no lookahead). Exits via a TP
             ladder (TP1/TP2/TP3): TP1 closes 50% and moves the stop to
             breakeven, TP2 closes another 25% and starts an ATR-multiple
             trailing stop on the remainder, TP3 (or the trailing stop) closes
             the rest.

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
from indicators import add_all_indicators, detect_ema_cross

BOT_FILE = os.path.join(os.path.dirname(__file__), "bots.json")
SIM_BARS = 500              # bars of recent history to seed a new bot with
MAX_FILLS = 60              # most-recent fills retained per bot for display
EVAL_THROTTLE = 20          # seconds between live refreshes
WARMUP_BARS = 210           # bars needed before indicators (EMA200 etc) are valid

_lock = threading.Lock()
_last_eval = 0.0

GRID_DEFAULTS = {"levels": 8, "order_size_usd": 100.0, "range_pct": 8.0}
DCA_DEFAULTS = {
    "base_order_usd": 100.0,
    "safety_order_usd": 100.0,
    "max_safety_orders": 5,
    "price_deviation_pct": 2.5,
    "take_profit_pct": 2.0,
    "stop_loss_pct": 15.0,   # cut the whole deal once safety orders are exhausted and price keeps falling this far below avg entry
}
SIGNAL_DEFAULTS = {
    "position_usd": 100.0,
    "min_confidence": 65,
    "trail_atr_mult": 1.5,   # ATR multiple used for the trailing stop on the TP2+ runner
}
TP_FRACTIONS = [0.5, 0.25, 0.25]  # of the original position size, closed at TP1/TP2/TP3


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
    if mode not in ("grid", "dca", "signal"):
        raise ValueError("mode must be 'grid', 'dca', or 'signal'")

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
    elif mode == "dca":
        cfg = {**DCA_DEFAULTS, **{k: config[k] for k in DCA_DEFAULTS if k in config}}
        cfg["base_order_usd"] = max(1.0, float(cfg["base_order_usd"]))
        cfg["safety_order_usd"] = max(1.0, float(cfg["safety_order_usd"]))
        cfg["max_safety_orders"] = max(0, min(20, int(cfg["max_safety_orders"])))
        cfg["price_deviation_pct"] = max(0.2, min(20.0, float(cfg["price_deviation_pct"])))
        cfg["take_profit_pct"] = max(0.2, min(20.0, float(cfg["take_profit_pct"])))
        cfg["stop_loss_pct"] = max(0.0, min(80.0, float(cfg["stop_loss_pct"])))
        state = {"deal": None}
    else:
        cfg = {**SIGNAL_DEFAULTS, **{k: config[k] for k in SIGNAL_DEFAULTS if k in config}}
        cfg["position_usd"] = max(1.0, float(cfg["position_usd"]))
        cfg["min_confidence"] = max(0, min(100, int(cfg["min_confidence"])))
        cfg["trail_atr_mult"] = max(0.2, min(10.0, float(cfg["trail_atr_mult"])))
        state = {"position": None, "pending_signal": None}

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
    elif bot["mode"] == "dca":
        _step_dca(bot, bars)
    else:
        _step_signal(bot, df, bars)

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
    sl_pct = cfg.get("stop_loss_pct", 0)
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

        # Stop-loss: once safety orders are exhausted, cut the deal rather than
        # hold an ever-worsening position with no more room to average down.
        if sl_pct and deal["safety_used"] >= cfg["max_safety_orders"]:
            stop_price = deal["avg"] * (1 - sl_pct / 100)
            if low <= stop_price:
                pnl = (stop_price - deal["avg"]) * deal["qty"]
                bot["realized_pnl"] += pnl
                bot["completed_trades"] += 1
                bot["fills"].append({
                    "time": ts.isoformat(), "side": "SELL", "price": round(stop_price, 8),
                    "qty": round(deal["qty"], 8), "usd": round(stop_price * deal["qty"], 2),
                })
                closed = {
                    "entry": round(deal["avg"], 8), "exit": round(stop_price, 8),
                    "qty": round(deal["qty"], 8), "pnl": round(pnl, 4),
                    "pnl_pct": round(-sl_pct, 3),
                    "safety_used": deal["safety_used"],
                    "opened_at": deal["opened_at"], "closed_at": ts.isoformat(),
                    "exit_reason": "stop_loss",
                }
                bot["closed_trades"].append(closed)
                new_closed.append(closed)
                st["deal"] = _open_deal(close, ts)
                continue

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
                "exit_reason": "take_profit",
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


def _step_signal(bot: dict, df: pd.DataFrame, bars: pd.DataFrame) -> None:
    """Trades the app's own EMA cross + confidence signal on closed candles,
    executing at the next candle's open. TP1/TP2/TP3 ladder with move-to-
    breakeven after TP1 and an ATR trailing stop on the runner after TP2."""
    from signals import generate_signal

    cfg = bot["config"]
    st = bot["state"]
    new_closed = []

    ind_df = add_all_indicators(df)
    idx_list = df.index

    for ts in bars.index:
        pos_in_full = idx_list.get_loc(ts)
        bar = df.iloc[pos_in_full]

        # 1) Consume a pending signal from the previous (closed) candle — enter
        #    at THIS bar's open, never the signal candle's own close.
        pending = st.get("pending_signal")
        if pending is not None and st.get("position") is None:
            _open_signal_position(bot, pending, float(bar["open"]), ts)
            st["pending_signal"] = None

        # 2) Manage an open position against this bar's high/low.
        position = st.get("position")
        if position is not None:
            atr_row = ind_df["atr"].iloc[pos_in_full]
            atr_now = float(atr_row) if pd.notna(atr_row) else position.get("atr_at_entry", 0.0)
            _manage_signal_position(bot, position, bar, ts, atr_now, cfg, new_closed)
            position = st.get("position")

        # 3) If flat, scan this closed candle for a fresh cross + confidence
        #    signal. Only accept a cross that happened exactly on this candle
        #    (candles_since == 0) so we never act on a stale/already-seen cross.
        if position is None and st.get("pending_signal") is None:
            if pos_in_full + 1 < WARMUP_BARS:
                continue
            window_ind = ind_df.iloc[: pos_in_full + 1]
            last_row = window_ind.iloc[-1]
            if last_row[["ema7", "ema25", "atr", "rsi"]].isna().any():
                continue
            direction, candles_since = detect_ema_cross(window_ind)
            if direction is None or candles_since != 0:
                continue
            raw_window = df.iloc[: pos_in_full + 1]
            try:
                sig = generate_signal(
                    raw_window, bot["symbol"], bot["timeframe"],
                    min_confidence=cfg["min_confidence"],
                )
            except Exception:
                sig = None
            if sig is None:
                continue
            st["pending_signal"] = {
                "direction": sig.direction.value,
                "stop_loss": float(sig.stop_loss),
                "tp_prices": [float(t.price) for t in sig.take_profits],
                "confidence": sig.confidence,
                "ai_probability": sig.ai_probability,
                "atr_at_entry": float(last_row["atr"]),
            }

    position = st.get("position")
    st["position_qty"] = round(position["qty_remaining"], 8) if position else 0.0
    st["position_cost"] = round(position["qty_remaining"] * position["entry_price"], 2) if position else 0.0
    st["avg_entry"] = round(position["entry_price"], 8) if position else None
    st["direction"] = position["direction"] if position else None
    bot["_new_closed"] = new_closed


def _open_signal_position(bot: dict, pending: dict, entry_price: float, ts) -> None:
    cfg = bot["config"]
    direction = pending["direction"]
    stop_loss = pending["stop_loss"]
    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        return
    qty = cfg["position_usd"] / entry_price
    position = {
        "direction": direction,
        "entry_price": entry_price,
        "entry_time": ts.isoformat(),
        "stop": stop_loss,
        "risk": risk,
        "tp_prices": pending["tp_prices"],
        "tp_hit": [False, False, False],
        "qty_total": qty,
        "qty_remaining": qty,
        "usd_total": cfg["position_usd"],
        "trailing_active": False,
        "confidence": pending["confidence"],
        "ai_probability": pending["ai_probability"],
        "atr_at_entry": pending["atr_at_entry"],
    }
    bot["state"]["position"] = position
    bot["fills"].append({
        "time": ts.isoformat(), "side": "BUY" if direction == "LONG" else "SELL_SHORT",
        "price": round(entry_price, 8), "qty": round(qty, 8), "usd": round(cfg["position_usd"], 2),
    })


def _finalize_signal_close(bot: dict, position: dict, ts, exit_reason: str, new_closed: list) -> None:
    is_long = position["direction"] == "LONG"
    weighted_exit = position.get("realized_cost_basis", 0.0)
    total_qty = position["qty_total"] - position["qty_remaining"]
    avg_exit = weighted_exit / total_qty if total_qty else position["entry_price"]
    result_r = position.get("realized_pnl", 0.0) / (position["risk"] * position["qty_total"]) if position["risk"] else 0.0
    closed = {
        "entry": round(position["entry_price"], 8),
        "exit": round(avg_exit, 8),
        "qty": round(total_qty, 8),
        "pnl": round(position.get("realized_pnl", 0.0), 4),
        "pnl_pct": round(
            (avg_exit / position["entry_price"] - 1) * 100 if is_long
            else (position["entry_price"] / avg_exit - 1) * 100, 3
        ),
        "direction": position["direction"],
        "stop_loss": position["stop"],
        "tp1": position["tp_prices"][0], "tp2": position["tp_prices"][1], "tp3": position["tp_prices"][2],
        "confidence": position["confidence"],
        "ai_probability": position["ai_probability"],
        "result_r": round(result_r, 3),
        "exit_reason": exit_reason,
        "opened_at": position["entry_time"],
        "closed_at": ts.isoformat(),
    }
    bot["closed_trades"].append(closed)
    new_closed.append(closed)
    bot["completed_trades"] += 1
    bot["state"]["position"] = None


def _manage_signal_position(bot: dict, position: dict, bar, ts, atr_now: float, cfg: dict, new_closed: list) -> None:
    is_long = position["direction"] == "LONG"
    low, high, close = float(bar["low"]), float(bar["high"]), float(bar["close"])

    def close_fraction(frac_of_total: float, price: float) -> None:
        qty = min(position["qty_total"] * frac_of_total, position["qty_remaining"])
        if qty <= 0:
            return
        pnl = (price - position["entry_price"]) * qty if is_long else (position["entry_price"] - price) * qty
        bot["realized_pnl"] += pnl
        position["qty_remaining"] -= qty
        position["realized_pnl"] = position.get("realized_pnl", 0.0) + pnl
        position["realized_cost_basis"] = position.get("realized_cost_basis", 0.0) + price * qty
        bot["fills"].append({
            "time": ts.isoformat(), "side": "SELL" if is_long else "BUY_COVER",
            "price": round(price, 8), "qty": round(qty, 8), "usd": round(price * qty, 2),
        })

    # 1) Stop-loss check first (conservative: if a candle touches both the
    #    stop and a target, the stop counts first).
    stop_hit = (low <= position["stop"]) if is_long else (high >= position["stop"])
    if stop_hit:
        close_fraction(1.0, position["stop"])
        reason = "breakeven_stop" if position["tp_hit"][0] and position["stop"] == position["entry_price"] else \
                 "trailing_stop" if position["trailing_active"] else "stop_loss"
        _finalize_signal_close(bot, position, ts, reason, new_closed)
        return

    # 2) TP ladder — partial closes, move to breakeven after TP1, start
    #    trailing the runner after TP2.
    for i, tp_price in enumerate(position["tp_prices"]):
        if position["tp_hit"][i]:
            continue
        hit = (high >= tp_price) if is_long else (low <= tp_price)
        if not hit:
            continue
        close_fraction(TP_FRACTIONS[i], tp_price)
        position["tp_hit"][i] = True
        if i == 0:
            position["stop"] = position["entry_price"]
        elif i == 1:
            position["trailing_active"] = True
        if position["qty_remaining"] <= 1e-12:
            _finalize_signal_close(bot, position, ts, f"tp{i + 1}", new_closed)
            return

    # 3) ATR trailing stop on the remainder once TP2 has been hit.
    if position["trailing_active"]:
        trail_dist = atr_now * cfg.get("trail_atr_mult", 1.5)
        if is_long:
            new_stop = close - trail_dist
            if new_stop > position["stop"]:
                position["stop"] = new_stop
        else:
            new_stop = close + trail_dist
            if new_stop < position["stop"]:
                position["stop"] = new_stop


# ---------------------------------------------------------------------------
# Refresh + public views
# ---------------------------------------------------------------------------
def _unrealized(bot: dict) -> float:
    st = bot["state"]
    qty = st.get("position_qty", 0.0)
    cost = st.get("position_cost", 0.0)
    if qty <= 0:
        return 0.0
    if bot["mode"] == "signal" and st.get("direction") == "SHORT":
        return round(cost - bot["last_price"] * qty, 4)
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
        "direction": st.get("direction"),
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
