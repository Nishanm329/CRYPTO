import { useState } from "react";
import useSWR from "swr";
import clsx from "clsx";
import { api, formatPrice } from "../lib/api";

const TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h", "1d"];
const pnlClass = (v) => (v > 0 ? "text-emerald-400" : v < 0 ? "text-red-400" : "text-tx-muted");

function Stat({ label, value, tone = "default" }) {
  const toneClass =
    tone === "pos" ? "text-emerald-400" :
    tone === "neg" ? "text-red-400" :
    tone === "gold" ? "text-brand-gold" : "text-tx";
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-[11px] uppercase tracking-wide text-tx-muted">{label}</div>
      <div className={clsx("text-2xl font-bold mt-1", toneClass)}>{value}</div>
    </div>
  );
}

function NumField({ label, value, onChange, step = "1" }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] text-tx-muted">{label}</span>
      <input
        type="number" step={step} value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-tx font-mono focus:border-brand-blue outline-none"
      />
    </label>
  );
}

function CreateBot({ defaultSymbol, onCreated }) {
  const [mode, setMode] = useState("grid");
  const [symbol, setSymbol] = useState((defaultSymbol || "BTCUSDT").replace("USDT", ""));
  const [timeframe, setTimeframe] = useState("1d");
  const [grid, setGrid] = useState({ levels: 8, order_size_usd: 100, range_pct: 8 });
  const [dca, setDca] = useState({ base_order_usd: 100, safety_order_usd: 100, max_safety_orders: 5, price_deviation_pct: 2.5, take_profit_pct: 2, stop_loss_pct: 15 });
  const [signal, setSignal] = useState({ position_usd: 100, min_confidence: 65, trail_atr_mult: 1.5 });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const config = mode === "grid"
        ? { levels: Number(grid.levels), order_size_usd: Number(grid.order_size_usd), range_pct: Number(grid.range_pct) }
        : mode === "dca"
        ? { base_order_usd: Number(dca.base_order_usd), safety_order_usd: Number(dca.safety_order_usd), max_safety_orders: Number(dca.max_safety_orders), price_deviation_pct: Number(dca.price_deviation_pct), take_profit_pct: Number(dca.take_profit_pct), stop_loss_pct: Number(dca.stop_loss_pct) }
        : { position_usd: Number(signal.position_usd), min_confidence: Number(signal.min_confidence), trail_atr_mult: Number(signal.trail_atr_mult) };
      await api.createBot(mode, symbol.toUpperCase(), timeframe, config);
      onCreated();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-bg-card border border-border rounded-xl p-4 space-y-3">
      <div className="text-xs font-semibold text-tx">New Paper-Trading Bot</div>
      <div className="flex gap-2">
        {["grid", "dca", "signal"].map((m) => (
          <button key={m} onClick={() => setMode(m)}
            className={clsx("px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors",
              mode === m ? "bg-brand-blue/15 border-brand-blue text-brand-blue" : "border-border text-tx-muted hover:text-tx")}>
            {m === "grid" ? "Grid" : m === "dca" ? "DCA" : "Signal"}
          </button>
        ))}
      </div>
      <p className="text-[11px] text-tx-muted">
        {mode === "grid"
          ? "Ladders buy levels across a range; sells each fill one grid step higher. Profits in ranging markets."
          : mode === "dca"
          ? "Buys a base order, averages down with safety orders, takes profit on the whole deal above the average entry. Stops out if safety orders run out and price keeps falling."
          : "Trades the app's own EMA cross + confidence signals. TP1/TP2/TP3 ladder: TP1 closes 50% and moves the stop to breakeven, TP2 closes 25% and starts an ATR trailing stop on the rest."}
      </p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-[11px] text-tx-muted">Symbol</span>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value)}
            className="bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-tx font-mono uppercase focus:border-brand-blue outline-none" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[11px] text-tx-muted">Timeframe</span>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}
            className="bg-bg border border-border rounded-lg px-2 py-1.5 text-xs text-tx focus:border-brand-blue outline-none">
            {TIMEFRAMES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        {mode === "grid" ? (
          <>
            <NumField label="Grid Levels" value={grid.levels} onChange={(v) => setGrid({ ...grid, levels: v })} />
            <NumField label="Order Size ($)" value={grid.order_size_usd} onChange={(v) => setGrid({ ...grid, order_size_usd: v })} />
            <NumField label="Range ±%" value={grid.range_pct} step="0.5" onChange={(v) => setGrid({ ...grid, range_pct: v })} />
          </>
        ) : mode === "dca" ? (
          <>
            <NumField label="Base Order ($)" value={dca.base_order_usd} onChange={(v) => setDca({ ...dca, base_order_usd: v })} />
            <NumField label="Safety Order ($)" value={dca.safety_order_usd} onChange={(v) => setDca({ ...dca, safety_order_usd: v })} />
            <NumField label="Max Safety Orders" value={dca.max_safety_orders} onChange={(v) => setDca({ ...dca, max_safety_orders: v })} />
            <NumField label="Deviation %" value={dca.price_deviation_pct} step="0.1" onChange={(v) => setDca({ ...dca, price_deviation_pct: v })} />
            <NumField label="Take Profit %" value={dca.take_profit_pct} step="0.1" onChange={(v) => setDca({ ...dca, take_profit_pct: v })} />
            <NumField label="Stop Loss %" value={dca.stop_loss_pct} step="0.5" onChange={(v) => setDca({ ...dca, stop_loss_pct: v })} />
          </>
        ) : (
          <>
            <NumField label="Position Size ($)" value={signal.position_usd} onChange={(v) => setSignal({ ...signal, position_usd: v })} />
            <NumField label="Min Confidence" value={signal.min_confidence} onChange={(v) => setSignal({ ...signal, min_confidence: v })} />
            <NumField label="Trail ATR ×" value={signal.trail_atr_mult} step="0.1" onChange={(v) => setSignal({ ...signal, trail_atr_mult: v })} />
          </>
        )}
      </div>
      {err && <div className="text-xs text-red-400">{err}</div>}
      <button onClick={submit} disabled={busy}
        className="px-4 py-2 rounded-lg bg-brand-blue text-white text-xs font-semibold hover:bg-blue-600 transition-colors disabled:opacity-50">
        {busy ? "Launching…" : "Launch Bot"}
      </button>
    </div>
  );
}

function BotCard({ bot, onChanged }) {
  const [open, setOpen] = useState(false);
  const total = (bot.realized_pnl || 0) + (bot.unrealized_pnl || 0);
  const act = async (fn) => { await fn(); onChanged(); };

  return (
    <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between px-4 py-3 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className={clsx("text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase shrink-0",
            bot.mode === "grid" ? "bg-brand-blue/15 text-brand-blue" :
            bot.mode === "dca" ? "bg-purple-500/15 text-purple-400" : "bg-amber-500/15 text-amber-400")}>
            {bot.mode}
          </span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-tx truncate">
              {bot.symbol.replace("USDT", "")}<span className="text-tx-muted font-normal">/USDT</span>
              <span className="text-tx-muted text-xs ml-2">{bot.timeframe}</span>
              {bot.mode === "signal" && bot.direction && (
                <span className={clsx("text-xs ml-2 font-semibold", bot.direction === "LONG" ? "text-emerald-400" : "text-red-400")}>
                  {bot.direction}
                </span>
              )}
            </div>
            <div className="text-[11px] text-tx-muted truncate">
              {bot.completed_trades} closed · {
                bot.mode === "grid" ? `${bot.open_levels} open levels` :
                bot.mode === "dca" ? `${bot.safety_used ?? 0} safety used` :
                bot.position_qty > 0 ? "in position" : "flat"
              }
              {" · "}<span className={bot.status === "running" ? "text-emerald-400" : "text-tx-muted"}>{bot.status}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between sm:justify-end gap-4 sm:shrink-0">
          <div className="text-left sm:text-right">
            <div className={clsx("text-base font-bold font-mono", pnlClass(total))}>
              {total >= 0 ? "+" : ""}${total.toFixed(2)}
            </div>
            <div className="text-[10px] text-tx-muted">
              R ${bot.realized_pnl.toFixed(2)} · U <span className={pnlClass(bot.unrealized_pnl)}>${bot.unrealized_pnl.toFixed(2)}</span>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {bot.status === "running"
              ? <button onClick={() => act(() => api.stopBot(bot.id))} className="text-[11px] px-2 py-1.5 rounded border border-border text-tx-muted hover:text-tx">Pause</button>
              : <button onClick={() => act(() => api.startBot(bot.id))} className="text-[11px] px-2 py-1.5 rounded border border-border text-emerald-400 hover:text-emerald-300">Resume</button>}
            <button onClick={() => act(() => api.deleteBot(bot.id))} className="text-[11px] px-2 py-1.5 rounded border border-border text-red-400 hover:text-red-300">Delete</button>
            <button onClick={() => setOpen(!open)} className="text-[11px] px-2 py-1.5 rounded border border-border text-tx-muted hover:text-tx">{open ? "Hide" : "Detail"}</button>
          </div>
        </div>
      </div>
      {open && (
        <div className="border-t border-border px-4 py-3 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="text-[11px] font-semibold text-tx mb-1.5">Recent Fills</div>
            <div className="space-y-1 max-h-48 overflow-y-auto no-scrollbar">
              {bot.fills.length === 0 && <div className="text-xs text-tx-muted">No fills yet.</div>}
              {bot.fills.map((f, i) => (
                <div key={i} className="flex items-center justify-between text-[11px]">
                  <span className={f.side.startsWith("BUY") ? "text-emerald-400 font-semibold" : "text-red-400 font-semibold"}>{f.side}</span>
                  <span className="font-mono text-tx">{formatPrice(f.price, bot.symbol)}</span>
                  <span className="font-mono text-tx-muted">${f.usd}</span>
                  <span className="text-tx-muted">{new Date(f.time).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="text-[11px] font-semibold text-tx mb-1.5">Closed Deals</div>
            <div className="space-y-1 max-h-48 overflow-y-auto no-scrollbar">
              {bot.closed_trades.length === 0 && <div className="text-xs text-tx-muted">No closed deals yet.</div>}
              {bot.closed_trades.map((t, i) => (
                <div key={i} className="flex items-center justify-between text-[11px]">
                  <span className="font-mono text-tx-muted">{formatPrice(t.entry, bot.symbol)}→{formatPrice(t.exit, bot.symbol)}</span>
                  {t.exit_reason && <span className="text-tx-muted uppercase text-[10px]">{t.exit_reason.replace(/_/g, " ")}</span>}
                  <span className={clsx("font-mono font-semibold", pnlClass(t.pnl))}>{t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}</span>
                  <span className={clsx("font-mono", pnlClass(t.pnl_pct))}>{t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function BotView({ defaultSymbol }) {
  const { data, error, isLoading, mutate } = useSWR("bots", () => api.bots(), {
    refreshInterval: 30000,
    revalidateOnFocus: false,
  });

  const bots = data?.bots || [];
  const sum = data?.summary || {};

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-purple-400" />
          <h1 className="text-lg font-bold text-tx">Trading Bots</h1>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-400 font-semibold">paper trading</span>
        </div>
        <p className="text-xs text-tx-muted mt-1">
          Grid, DCA &amp; Signal bots simulated against real Binance price action — no API keys, no live orders.
          Closed deals are logged into the verified track record.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Total P&L" value={`${(sum.total_pnl ?? 0) >= 0 ? "+" : ""}$${(sum.total_pnl ?? 0).toFixed(2)}`} tone={(sum.total_pnl ?? 0) >= 0 ? "gold" : "neg"} />
        <Stat label="Realized" value={`${(sum.realized_pnl ?? 0) >= 0 ? "+" : ""}$${(sum.realized_pnl ?? 0).toFixed(2)}`} tone={(sum.realized_pnl ?? 0) >= 0 ? "pos" : "neg"} />
        <Stat label="Closed Deals" value={sum.completed_trades ?? 0} />
        <Stat label="Active Bots" value={`${sum.running ?? 0} / ${sum.bots ?? 0}`} />
      </div>

      <CreateBot defaultSymbol={defaultSymbol} onCreated={() => mutate()} />

      {error && <div className="text-xs text-red-400">Failed to load bots: {String(error.message || error)}</div>}
      {isLoading && bots.length === 0 && (
        <div className="flex items-center justify-center py-10 text-tx-muted">
          <div className="animate-spin w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full" />
        </div>
      )}

      <div className="space-y-3">
        {bots.map((b) => <BotCard key={b.id} bot={b} onChanged={() => mutate()} />)}
        {!isLoading && bots.length === 0 && (
          <div className="text-center text-xs text-tx-muted py-8">No bots yet — launch one above to start paper trading.</div>
        )}
      </div>
    </div>
  );
}
