import { useState } from "react";
import useSWR from "swr";
import { api, formatPrice, formatChange } from "../lib/api";
import clsx from "clsx";

// Kronos inference runs one pair at a time (tens of seconds each on CPU), so
// keep the pair counts modest. The scan runs in the background and fills in live.
const PAIR_OPTIONS = [10, 20, 50];
const HORIZONS = [12, 24, 48];

function pct(v) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function KronosCard({ r, selected, onClick, predLen, timeframe }) {
  const up = r.direction === "UP";
  const down = r.direction === "DOWN";
  const tone = up ? "text-brand-green" : down ? "text-brand-red" : "text-tx-muted";
  // Bar width: predicted move scaled so ±5% fills the track.
  const width = Math.min(100, (Math.abs(r.pred_change_pct) / 5) * 100);

  return (
    <div
      onClick={onClick}
      className={clsx(
        "p-3 rounded-xl border cursor-pointer transition-all",
        selected ? "bg-brand-blue/10 border-brand-blue/40" : "bg-bg-card border-border hover:border-border-light"
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className="text-sm font-bold text-tx">{r.symbol.replace("USDT", "")}</span>
          <span className="text-tx-muted text-xs">/USDT</span>
        </div>
        <span
          className={clsx(
            "text-xs font-bold px-2 py-0.5 rounded-full",
            up ? "bg-brand-green/15 text-brand-green" : down ? "bg-brand-red/15 text-brand-red" : "bg-border text-tx-muted"
          )}
        >
          {up ? "▲ UP" : down ? "▼ DOWN" : "● FLAT"}
        </span>
      </div>

      <div className="text-xs font-mono text-tx mb-2">
        ${formatPrice(r.price)}
        <span className={clsx("ml-2", r.change_24h >= 0 ? "text-brand-green" : "text-brand-red")}>
          {formatChange(r.change_24h)}
        </span>
      </div>

      {/* Predicted move */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex-1 mr-3">
          <div className="h-1 bg-bg rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{ width: `${width}%`, backgroundColor: up ? "#22c55e" : down ? "#ef4444" : "#64748b" }}
            />
          </div>
        </div>
        <span className={clsx("text-xs font-bold font-mono", tone)}>{pct(r.pred_change_pct)}</span>
      </div>

      <div className="grid grid-cols-3 gap-1 text-[10px] mb-2">
        <div className="bg-bg/60 rounded px-1.5 py-1">
          <div className="text-tx-muted">Target</div>
          <div className="font-mono text-tx">${formatPrice(r.pred_close)}</div>
        </div>
        <div className="bg-bg/60 rounded px-1.5 py-1">
          <div className="text-tx-muted">Max up</div>
          <div className="font-mono text-brand-green">{pct(r.pred_upside_pct)}</div>
        </div>
        <div className="bg-bg/60 rounded px-1.5 py-1">
          <div className="text-tx-muted">Max down</div>
          <div className="font-mono text-brand-red">{pct(r.pred_downside_pct)}</div>
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px]">
        <span className="text-tx-muted">Next {predLen} × {timeframe}</span>
        {r.agrees_with_ema === true && (
          <span className="px-1.5 py-0.5 rounded bg-brand-green/15 text-brand-green border border-brand-green/30">
            ✓ Agrees with EMA {r.ema_direction} {r.ema_confidence}%
          </span>
        )}
        {r.agrees_with_ema === false && (
          <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30">
            ✗ Against EMA {r.ema_direction}
          </span>
        )}
        {r.agrees_with_ema == null && <span className="text-tx-muted">No EMA signal</span>}
      </div>
    </div>
  );
}

export default function KronosScanPanel({ timeframe, filterDir, onSelectSymbol, selectedSymbol }) {
  const [pairs, setPairs] = useState(20);
  const [predLen, setPredLen] = useState(24);
  const [sortKey, setSortKey] = useState("move");
  const [agreeOnly, setAgreeOnly] = useState(false);

  const { data, error, isLoading } = useSWR(
    `kronos-scan-${timeframe}-${pairs}-${predLen}`,
    () => api.kronosScan(timeframe, pairs, predLen),
    {
      // Poll while the background scan is running so cards fill in live.
      refreshInterval: (latest) => (latest?.warming || latest?.refreshing ? 5000 : 120000),
      revalidateOnFocus: false,
      dedupingInterval: 3000,
      shouldRetryOnError: false,
    }
  );

  const notInstalled = error && /not installed|501/i.test(error.message);
  const warming = data?.warming === true;
  const progress = data?.progress ?? { done: 0, total: 0 };

  const dirMap = { LONG: "UP", SHORT: "DOWN" };
  const results = (data?.results ?? [])
    .filter((r) => filterDir === "ALL" || r.direction === dirMap[filterDir])
    .filter((r) => !agreeOnly || r.agrees_with_ema === true)
    .sort((a, b) => {
      if (sortKey === "up") return b.pred_change_pct - a.pred_change_pct;
      if (sortKey === "down") return a.pred_change_pct - b.pred_change_pct;
      if (sortKey === "volume") return b.volume_24h - a.volume_24h;
      return Math.abs(b.pred_change_pct) - Math.abs(a.pred_change_pct);
    });

  return (
    <div className="flex flex-col gap-3">
      {/* Kronos controls */}
      <div className="flex items-center gap-1.5 flex-wrap text-xs">
        <span className="text-tx-muted">Pairs</span>
        {PAIR_OPTIONS.map((n) => (
          <button key={n} onClick={() => setPairs(n)}
            className={clsx("px-2 py-1 rounded-lg font-semibold transition-all",
              pairs === n ? "bg-purple-500 text-white" : "text-tx-muted hover:text-tx")}
          >{n}</button>
        ))}
        <div className="w-px h-4 bg-border mx-1" />
        <span className="text-tx-muted">Horizon</span>
        {HORIZONS.map((h) => (
          <button key={h} onClick={() => setPredLen(h)}
            className={clsx("px-2 py-1 rounded-lg font-semibold transition-all",
              predLen === h ? "bg-purple-500 text-white" : "text-tx-muted hover:text-tx")}
          >{h} bars</button>
        ))}
        <div className="w-px h-4 bg-border mx-1" />
        {[["move", "Biggest move"], ["up", "Most up"], ["down", "Most down"], ["volume", "Volume"]].map(([k, l]) => (
          <button key={k} onClick={() => setSortKey(k)}
            className={clsx("px-2 py-1 rounded-lg transition-all",
              sortKey === k ? "bg-border text-tx" : "text-tx-muted hover:text-tx")}
          >{l}</button>
        ))}
        <button onClick={() => setAgreeOnly((v) => !v)}
          className={clsx("px-2 py-1 rounded-lg transition-all border",
            agreeOnly ? "bg-brand-green/15 text-brand-green border-brand-green/30" : "text-tx-muted border-border hover:text-tx")}
        >✓ Agrees with EMA</button>
      </div>

      {data && !notInstalled && (
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="font-bold px-2.5 py-1 rounded-full bg-brand-green/15 text-brand-green">▲ {data.up_count} Up</span>
          <span className="font-bold px-2.5 py-1 rounded-full bg-brand-red/15 text-brand-red">▼ {data.down_count} Down</span>
          <span className="px-2.5 py-1 rounded-full bg-border text-tx-muted">● {data.flat_count} Flat</span>
          <span className="text-tx-muted">{data.model?.split("/").pop()}</span>
          {data.refreshing && !warming && <span className="text-purple-400">Refreshing…</span>}
        </div>
      )}

      {/* Progress while the background scan runs */}
      {warming && (
        <div className="bg-bg-card border border-border rounded-xl p-3">
          <div className="flex items-center gap-2 text-xs text-tx-muted mb-2">
            <div className="w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            Kronos is forecasting {progress.total || pairs} pairs · {progress.done}/{progress.total || "…"} done
          </div>
          <div className="h-1 bg-bg rounded-full overflow-hidden">
            <div className="h-full bg-purple-500 transition-all"
              style={{ width: `${progress.total ? (progress.done / progress.total) * 100 : 3}%` }} />
          </div>
          <div className="text-[10px] text-tx-muted mt-2">
            Each pair takes a few seconds on GPU, longer on CPU. Results appear as they finish.
          </div>
        </div>
      )}

      {notInstalled && (
        <div className="bg-bg-card border border-border rounded-xl p-4 text-xs text-tx-muted">
          <div className="text-sm font-semibold text-tx mb-1">Kronos isn't installed on this backend</div>
          Run <code className="text-purple-400">backend/scripts/install_kronos.sh --cpu</code> and restart the
          backend, or rebuild the Docker image with <code className="text-purple-400">INSTALL_KRONOS=1</code>.
        </div>
      )}
      {error && !notInstalled && (
        <div className="text-xs text-brand-red">Kronos scan failed: {error.message}</div>
      )}
      {isLoading && !data && !error && (
        <div className="flex items-center justify-center h-32 gap-2 text-tx-muted text-sm">
          <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
          Starting Kronos scan…
        </div>
      )}

      {data && !warming && results.length === 0 && (
        <div className="flex flex-col items-center justify-center h-32 text-tx-muted text-sm">
          No pairs match these filters
        </div>
      )}

      {results.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {results.map((r) => (
            <KronosCard
              key={r.symbol}
              r={r}
              predLen={data.pred_len}
              timeframe={timeframe}
              selected={selectedSymbol === r.symbol}
              onClick={() => onSelectSymbol?.(r.symbol)}
            />
          ))}
        </div>
      )}

      {data && (
        <div className="text-[10px] text-tx-muted">{data.disclaimer}</div>
      )}
    </div>
  );
}
