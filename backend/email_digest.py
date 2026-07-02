"""
Per-component email digests.

Each dashboard component (signals, scanner, track-record, market) can have its own
email schedule: an on/off toggle, recipient, cadence, and filters. Configs are stored
in a JSON file (consistent with the rest of this DB-free service) so the schedule is
readable server-side and survives process restarts. An external cron hits
POST /api/email/run on an interval; run_due() then sends any digest whose cadence has
elapsed. Sending uses plain SMTP (env-configured) so no third-party SDK is required.
"""
import os
import re
import json
import time
import asyncio
import smtplib
import threading
from email.message import EmailMessage
from datetime import datetime, timezone

from scanner import scan_market
from track_record import get_stats
from binance_client import get_top_volume_pairs, batch_get_tickers

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "email_configs.json")
_lock = threading.Lock()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Cooldown between manual "send test now" calls per component, to stop the
# shared demo API key from being used to spam a recipient via repeated test sends.
TEST_COOLDOWN_SECONDS = 30


def _validate_recipient(recipient: str) -> None:
    if recipient and not EMAIL_RE.match(recipient):
        raise ValueError(f"Invalid recipient email address: {recipient}")

# Components that support an email digest and their default filter set.
COMPONENTS = {
    "signals": {"timeframe": "1h", "min_confidence": 60, "direction": "ALL", "top_n": 10},
    "scanner": {"timeframe": "1h", "min_confidence": 55, "direction": "ALL", "top_n": 15},
    "track-record": {},
    "market": {"top_n": 12},
}

# Cadence label -> seconds. A digest fires when (now - last_sent) >= its interval.
FREQUENCIES = {
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}
DEFAULT_FREQUENCY = "1d"


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def _load() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(configs: dict) -> None:
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(configs, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def _normalize(component: str, cfg: dict) -> dict:
    """Merge a stored/incoming config with safe defaults for the component."""
    filters = {**COMPONENTS.get(component, {}), **(cfg.get("filters") or {})}
    freq = cfg.get("frequency", DEFAULT_FREQUENCY)
    if freq not in FREQUENCIES:
        freq = DEFAULT_FREQUENCY
    return {
        "component": component,
        "enabled": bool(cfg.get("enabled", False)),
        "recipient": (cfg.get("recipient") or "").strip(),
        "frequency": freq,
        "filters": filters,
        "last_sent": float(cfg.get("last_sent", 0) or 0),
        "last_test_sent": float(cfg.get("last_test_sent", 0) or 0),
        "updated_at": cfg.get("updated_at"),
    }


def get_config(component: str) -> dict:
    with _lock:
        configs = _load()
    return _normalize(component, configs.get(component, {}))


def list_configs() -> list:
    with _lock:
        configs = _load()
    return [_normalize(c, configs.get(c, {})) for c in COMPONENTS]


def upsert_config(component: str, data: dict) -> dict:
    if component not in COMPONENTS:
        raise ValueError(f"Unknown component: {component}")
    recipient = data.get("recipient")
    if recipient is not None:
        _validate_recipient(recipient.strip())
    with _lock:
        configs = _load()
        existing = configs.get(component, {})
        merged = {
            **existing,
            "enabled": data.get("enabled", existing.get("enabled", False)),
            "recipient": data.get("recipient", existing.get("recipient", "")),
            "frequency": data.get("frequency", existing.get("frequency", DEFAULT_FREQUENCY)),
            "filters": {**(existing.get("filters") or {}), **(data.get("filters") or {})},
            "last_sent": existing.get("last_sent", 0),
            "last_test_sent": existing.get("last_test_sent", 0),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        configs[component] = _normalize(component, merged)
        _save(configs)
        return configs[component]


def _mark_sent(component: str) -> None:
    with _lock:
        configs = _load()
        cfg = configs.get(component, {})
        cfg["last_sent"] = time.time()
        configs[component] = _normalize(component, cfg)
        _save(configs)


def _mark_test_sent(component: str) -> None:
    with _lock:
        configs = _load()
        cfg = configs.get(component, {})
        cfg["last_test_sent"] = time.time()
        configs[component] = _normalize(component, cfg)
        _save(configs)


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------
def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def _send_smtp(recipient: str, subject: str, html: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", user)
    if not (host and user and password):
        raise RuntimeError("SMTP is not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD).")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content("This is an HTML email; please view it in an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


# ---------------------------------------------------------------------------
# Digest content
# ---------------------------------------------------------------------------
def _wrap(title: str, body: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0b0e11;color:#e6e8eb;padding:24px;">
      <div style="max-width:640px;margin:0 auto;background:#12161c;border:1px solid #232a33;border-radius:14px;overflow:hidden;">
        <div style="padding:18px 22px;border-bottom:1px solid #232a33;">
          <div style="font-size:16px;font-weight:700;">{title}</div>
          <div style="font-size:12px;color:#8b95a1;margin-top:2px;">CryptoSignal AI · {ts}</div>
        </div>
        <div style="padding:18px 22px;">{body}</div>
        <div style="padding:14px 22px;border-top:1px solid #232a33;font-size:11px;color:#6b7480;">
          You receive this because an email schedule is enabled for this component. Manage it in the app.
        </div>
      </div>
    </div>
    """


def _signal_rows(signals) -> str:
    if not signals:
        return '<div style="color:#8b95a1;font-size:13px;">No qualifying signals at this time.</div>'
    rows = ""
    for s in signals:
        d = s.direction.value if hasattr(s.direction, "value") else s.direction
        color = "#22c55e" if d == "LONG" else "#ef4444"
        arrow = "&#9650;" if d == "LONG" else "&#9660;"
        rows += f"""
        <tr style="border-bottom:1px solid #1d242c;">
          <td style="padding:8px 6px;font-weight:600;">{s.symbol.replace('USDT','')}<span style="color:#6b7480;">/USDT</span></td>
          <td style="padding:8px 6px;color:{color};font-weight:700;">{arrow} {d}</td>
          <td style="padding:8px 6px;text-align:right;font-family:monospace;">${s.price:,.4f}</td>
          <td style="padding:8px 6px;text-align:right;font-weight:700;">{s.confidence}%</td>
          <td style="padding:8px 6px;text-align:right;color:#8b95a1;">{int(round(s.ai_probability*100))}% AI</td>
          <td style="padding:8px 6px;text-align:right;color:#8b95a1;">R:R {s.rr_ratio}</td>
        </tr>"""
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="color:#6b7480;text-align:left;font-size:11px;">
        <th style="padding:6px;">PAIR</th><th style="padding:6px;">DIR</th>
        <th style="padding:6px;text-align:right;">PRICE</th><th style="padding:6px;text-align:right;">CONF</th>
        <th style="padding:6px;text-align:right;">AI</th><th style="padding:6px;text-align:right;">R:R</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


async def _build_signals(cfg: dict):
    f = cfg["filters"]
    tf = f.get("timeframe", "1h")
    min_conf = int(f.get("min_confidence", 60))
    direction = (f.get("direction") or "ALL").upper()
    top_n = int(f.get("top_n", 10))

    resp = await scan_market(timeframe=tf, max_pairs=100, min_confidence=min_conf)
    sigs = list(resp.signals)
    if direction in ("LONG", "SHORT"):
        sigs = [s for s in sigs if (s.direction.value if hasattr(s.direction, "value") else s.direction) == direction]
    sigs = sigs[:top_n]

    label = "Market Scanner" if cfg["component"] == "scanner" else "Live Signals"
    subject = f"[CryptoSignal] {label}: {len(sigs)} {direction.lower() if direction!='ALL' else ''} signals ({tf})".replace("  ", " ")
    summary = (
        f'<div style="font-size:13px;color:#8b95a1;margin-bottom:12px;">'
        f'Top {len(sigs)} of {resp.total_scanned} pairs scanned · {tf} · min confidence {min_conf}%'
        f'</div>'
    )
    return subject, _wrap(label, summary + _signal_rows(sigs))


async def _build_track_record(cfg: dict):
    stats = get_stats()
    cards = [
        ("Win Rate", f'{stats["win_rate"]}%'),
        ("Avg R / Trade", f'{stats["avg_r"]:+}'),
        ("Total R", f'{stats["total_r"]:+}'),
        ("Profit Factor", f'{stats["profit_factor"]}'),
        ("Closed", f'{stats["closed"]} ({stats["wins"]}W / {stats["losses"]}L)'),
        ("Max Drawdown", f'{stats["max_drawdown_r"]} R'),
    ]
    grid = '<div style="display:flex;flex-wrap:wrap;gap:10px;">'
    for label, val in cards:
        grid += (
            f'<div style="flex:1 1 30%;min-width:140px;background:#0b0e11;border:1px solid #232a33;'
            f'border-radius:10px;padding:12px;">'
            f'<div style="font-size:11px;color:#6b7480;text-transform:uppercase;">{label}</div>'
            f'<div style="font-size:18px;font-weight:700;margin-top:4px;">{val}</div></div>'
        )
    grid += "</div>"
    subject = f'[CryptoSignal] Track Record: {stats["win_rate"]}% win rate over {stats["closed"]} trades'
    return subject, _wrap("Verified Track Record", grid)


async def _build_market(cfg: dict):
    top_n = int(cfg["filters"].get("top_n", 12))
    pairs = await get_top_volume_pairs(top_n)
    data = await batch_get_tickers(pairs)
    rows = ""
    for sym in pairs:
        t = data.get(sym)
        if not t:
            continue
        chg = float(t["priceChangePercent"])
        color = "#22c55e" if chg >= 0 else "#ef4444"
        rows += f"""
        <tr style="border-bottom:1px solid #1d242c;">
          <td style="padding:8px 6px;font-weight:600;">{sym.replace('USDT','')}<span style="color:#6b7480;">/USDT</span></td>
          <td style="padding:8px 6px;text-align:right;font-family:monospace;">${float(t['lastPrice']):,.4f}</td>
          <td style="padding:8px 6px;text-align:right;color:{color};font-weight:700;">{chg:+.2f}%</td>
        </tr>"""
    table = f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="color:#6b7480;text-align:left;font-size:11px;">
        <th style="padding:6px;">PAIR</th><th style="padding:6px;text-align:right;">PRICE</th>
        <th style="padding:6px;text-align:right;">24H</th>
      </tr></thead><tbody>{rows}</tbody></table>"""
    subject = f"[CryptoSignal] Market Overview: top {top_n} by volume"
    return subject, _wrap("Market Overview", table)


_BUILDERS = {
    "signals": _build_signals,
    "scanner": _build_signals,
    "track-record": _build_track_record,
    "market": _build_market,
}


async def build_digest(component: str, cfg: dict):
    builder = _BUILDERS.get(component)
    if builder is None:
        raise ValueError(f"No digest builder for component: {component}")
    return await builder(cfg)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------
async def send_now(component: str) -> dict:
    """Build and send a digest for one component immediately (test/send button)."""
    cfg = get_config(component)
    if not cfg["recipient"]:
        raise ValueError("No recipient configured.")
    _validate_recipient(cfg["recipient"])
    wait = TEST_COOLDOWN_SECONDS - (time.time() - cfg["last_test_sent"])
    if wait > 0:
        raise ValueError(f"Please wait {int(wait) + 1}s before sending another test for this component.")
    subject, html = await build_digest(component, cfg)
    await asyncio.to_thread(_send_smtp, cfg["recipient"], subject, html)
    _mark_test_sent(component)
    return {"component": component, "recipient": cfg["recipient"], "sent": True}


async def run_due() -> dict:
    """Send every enabled digest whose cadence has elapsed. Called by the cron."""
    now = time.time()
    sent, skipped, errors = [], [], []
    for cfg in list_configs():
        component = cfg["component"]
        if not cfg["enabled"] or not cfg["recipient"]:
            skipped.append(component)
            continue
        interval = FREQUENCIES.get(cfg["frequency"], FREQUENCIES[DEFAULT_FREQUENCY])
        # 60s slack so a slightly-early cron tick still fires on schedule.
        if now - cfg["last_sent"] < interval - 60:
            skipped.append(component)
            continue
        try:
            subject, html = await build_digest(component, cfg)
            await asyncio.to_thread(_send_smtp, cfg["recipient"], subject, html)
            _mark_sent(component)
            sent.append(component)
        except Exception as e:
            errors.append({"component": component, "error": str(e)})
    return {"sent": sent, "skipped": skipped, "errors": errors, "ran_at": datetime.now(timezone.utc).isoformat()}
