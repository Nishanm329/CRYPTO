import { useState } from "react";
import useSWR from "swr";
import clsx from "clsx";
import { api, formatVolume } from "../lib/api";

const PRESETS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX"];

// Lightweight dependency-free sparkline.
function Sparkline({ data, color = "#3d7fff", height = 34 }) {
  if (!data || data.length < 2) return null;
  const vals = data.map((d) => d.v);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const w = 100;
  const pts = vals
    .map((v, i) => {
      const x = (i / (vals.length - 1)) * w;
      const y = height - ((v - min) / range) * (height - 2) - 1;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Card({ title, hint, children }) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-xs font-semibold text-tx">{title}</div>
        {hint && <div className="text-[10px] text-tx-muted">{hint}</div>}
      </div>
      {children}
    </div>
  );
}

// A long/short ratio rendered as a split bar (long green vs short red).
function RatioBar({ label, ratio }) {
  if (ratio == null) return null;
  const longPct = (ratio / (1 + ratio)) * 100;
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-tx-muted">{label}</span>
        <span className="text-[11px] font-mono text-tx">{ratio.toFixed(2)}</span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden bg-border">
        <div className="bg-brand-green" style={{ width: `${longPct}%` }} />
        <div className="bg-brand-red" style={{ width: `${100 - longPct}%` }} />
      </div>
    </div>
  );
}

function fmtCountdown(ms) {
  if (!ms || ms <= 0) return "—";
  const m = Math.floor(ms / 60000);
  const h = Math.floor(m / 60);
  return h > 0 ? `${h}h ${m % 60}m` : `${m}m`;
}

export default function DerivativesView({ defaultSymbol = "BTC" }) {
  const [symbol, setSymbol] = useState((defaultSymbol || "BTC").replace("USDT", "").toUpperCase());

  const { data, error, isLoading } = useSWR(
    `derivatives-${symbol}`,
    () => api.derivatives(symbol),
    { refreshInterval: 30000, revalidateOnFocus: false }
  );

  const funding = data?.funding;
  const oi = data?.open_interest;
  const ls = data?.long_short;
  const ob = data?.orderbook;

  const fundingPos = (funding?.current ?? 0) >= 0;
  const oiUp = (oi?.change_pct_24h ?? 0) >= 0;
  const imbalance = ob?.imbalance ?? 0; // [-1, 1]
  const buyPct = ((imbalance + 1) / 2) * 100;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 border-b border-border px-5 py-3">
        <h1 className="text-sm font-bold text-tx">Derivatives</h1>
        <p className="text-xs text-tx-muted mt-0.5">Funding, open interest & positioning from Binance perpetuals.</p>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-4 sm:p-5 flex flex-col gap-4 max-w-3xl mx-auto w-full">
        {/* Symbol selector */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar -mx-1 px-1">
          {PRESETS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={clsx(
                "shrink-0 min-w-[52px] px-3 py-2 md:py-1.5 rounded-lg text-xs font-semibold transition-all",
                symbol === s ? "bg-brand-blue text-white" : "bg-bg-card/60 text-tx-muted hover:text-tx active:bg-border"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {error && (
          <div className="text-center py-12 text-tx-muted border border-border border-dashed rounded-xl">
            <div className="text-xs font-medium text-tx mb-1">No perpetual market for {symbol}</div>
            <div className="text-xs text-tx-muted">Try a major pair like BTC, ETH or SOL.</div>
          </div>
        )}

        {!error && isLoading && !data && (
          <div className="text-center py-12 text-tx-muted text-xs">Loading {symbol} derivatives…</div>
        )}

        {!error && data && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Funding */}
            <Card title="Funding Rate" hint={funding?.next_funding_time ? `next in ${fmtCountdown(funding.next_funding_time - Date.now())}` : null}>
              <div className="flex items-end justify-between gap-3">
                <div>
                  <div className={clsx("text-2xl font-bold font-mono", fundingPos ? "text-brand-green" : "text-brand-red")}>
                    {fundingPos ? "+" : ""}{((funding?.current ?? 0) * 100).toFixed(4)}%
                  </div>
                  <div className="text-[11px] text-tx-muted mt-0.5">
                    {fundingPos ? "Longs pay shorts" : "Shorts pay longs"} · {(funding?.annualized_pct ?? 0).toFixed(1)}% APR
                  </div>
                </div>
              </div>
              <Sparkline data={funding?.history} color={fundingPos ? "#22c55e" : "#ef4444"} />
            </Card>

            {/* Open Interest */}
            <Card title="Open Interest" hint="24h trend">
              <div className="flex items-end justify-between gap-3">
                <div className="text-2xl font-bold font-mono text-tx">{oi?.value_usd != null ? formatVolume(oi.value_usd) : "—"}</div>
                {oi?.change_pct_24h != null && (
                  <div className={clsx("text-sm font-bold font-mono", oiUp ? "text-brand-green" : "text-brand-red")}>
                    {oiUp ? "▲" : "▼"} {Math.abs(oi.change_pct_24h).toFixed(2)}%
                  </div>
                )}
              </div>
              <Sparkline data={oi?.history} color={oiUp ? "#22c55e" : "#ef4444"} />
            </Card>

            {/* Long/Short positioning */}
            <Card title="Long / Short Ratio" hint="accounts">
              <div className="flex flex-col gap-2.5">
                <RatioBar label="Crowd (all accounts)" ratio={ls?.global} />
                <RatioBar label="Smart money (top traders)" ratio={ls?.top} />
                <RatioBar label="Taker flow (buy/sell)" ratio={ls?.taker} />
              </div>
              {ls?.smart_divergence != null && (
                <div className="text-[11px] mt-1">
                  <span className="text-tx-muted">Smart vs crowd: </span>
                  <span className={clsx("font-semibold", ls.smart_divergence >= 0 ? "text-brand-green" : "text-brand-red")}>
                    {ls.smart_divergence >= 0 ? "Smart money more long" : "Crowd more long (contrarian)"}
                  </span>
                </div>
              )}
            </Card>

            {/* Order book imbalance */}
            <Card title="Order Book Imbalance" hint="top 100 levels">
              <div className="flex items-end justify-between gap-3">
                <div className={clsx("text-2xl font-bold font-mono", imbalance >= 0 ? "text-brand-green" : "text-brand-red")}>
                  {imbalance >= 0 ? "+" : ""}{(imbalance * 100).toFixed(1)}%
                </div>
                <div className="text-[11px] text-tx-muted">{imbalance >= 0 ? "Resting buy pressure" : "Resting sell pressure"}</div>
              </div>
              <div className="flex h-2.5 rounded-full overflow-hidden bg-border">
                <div className="bg-brand-green" style={{ width: `${buyPct}%` }} />
                <div className="bg-brand-red" style={{ width: `${100 - buyPct}%` }} />
              </div>
              <div className="flex justify-between text-[10px] text-tx-muted">
                <span>Bids {ob?.bid_vol != null ? formatVolume(ob.bid_vol) : "—"}</span>
                <span>Asks {ob?.ask_vol != null ? formatVolume(ob.ask_vol) : "—"}</span>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
