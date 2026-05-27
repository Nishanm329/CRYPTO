import { useState } from "react";
import { formatPrice, formatVolume, formatChange, confidenceColor, confidenceLabel } from "../lib/api";
import clsx from "clsx";

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "3d", "1w"];

function ConfidenceBar({ value }) {
  const color = confidenceColor(value);
  return (
    <div className="flex items-center gap-2">
      <div className="conf-bar-track w-16">
        <div
          className="conf-bar-fill"
          style={{ width: `${value}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono" style={{ color }}>
        {value}%
      </span>
    </div>
  );
}

function AIProbBadge({ prob }) {
  const pct = Math.round(prob * 100);
  const color = pct >= 65 ? "#22c55e" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <span className="text-xs font-mono font-bold" style={{ color }}>
      {pct}%
    </span>
  );
}

export default function Scanner({ scanData, loading, onSelectSymbol, selectedSymbol, timeframe, onTimeframeChange }) {
  const [sortKey, setSortKey] = useState("confidence");
  const [filterDir, setFilterDir] = useState("ALL");
  const [minConf, setMinConf] = useState(0);

  const signals = scanData?.signals ?? [];
  const filtered = signals
    .filter((s) => filterDir === "ALL" || s.direction === filterDir)
    .filter((s) => s.confidence >= minConf)
    .sort((a, b) => {
      if (sortKey === "confidence") return b.confidence - a.confidence;
      if (sortKey === "ai_prob") return b.ai_probability - a.ai_probability;
      if (sortKey === "volume") return b.volume_24h - a.volume_24h;
      if (sortKey === "change") return Math.abs(b.change_24h) - Math.abs(a.change_24h);
      return 0;
    });

  return (
    <div className="card flex flex-col h-full gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="live-dot" />
          <span className="text-sm font-semibold text-slate-200">Market Scanner</span>
          {scanData && (
            <span className="text-xs text-slate-500">
              {scanData.total_scanned} pairs · {scanData.scan_duration_ms}ms
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {["LONG", "SHORT", "ALL"].map((d) => (
            <button
              key={d}
              onClick={() => setFilterDir(d)}
              className={clsx("tab-btn", filterDir === d ? "tab-btn-active" : "tab-btn-inactive")}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Timeframe selector */}
      <div className="flex items-center gap-1 flex-wrap">
        <span className="text-xs text-slate-500 mr-1">TF:</span>
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => onTimeframeChange(tf)}
            className={clsx(
              "px-2 py-1 rounded text-xs font-medium transition-colors",
              timeframe === tf
                ? "bg-brand-blue text-white"
                : "bg-surface-2 text-slate-400 hover:text-slate-200"
            )}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Stats row */}
      {scanData && (
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-surface-2/50 rounded-lg p-2 text-center">
            <div className="text-xs text-slate-500">Signals</div>
            <div className="text-sm font-bold text-slate-200">{signals.length}</div>
          </div>
          <div className="bg-green-500/10 rounded-lg p-2 text-center border border-green-500/20">
            <div className="text-xs text-slate-500">Long</div>
            <div className="text-sm font-bold text-brand-green">{scanData.long_count}</div>
          </div>
          <div className="bg-red-500/10 rounded-lg p-2 text-center border border-red-500/20">
            <div className="text-xs text-slate-500">Short</div>
            <div className="text-sm font-bold text-brand-red">{scanData.short_count}</div>
          </div>
        </div>
      )}

      {/* Sort controls */}
      <div className="flex items-center gap-1 flex-wrap text-xs">
        <span className="text-slate-500">Sort:</span>
        {[
          { k: "confidence", l: "Confidence" },
          { k: "ai_prob", l: "AI Score" },
          { k: "volume", l: "Volume" },
          { k: "change", l: "Change" },
        ].map(({ k, l }) => (
          <button
            key={k}
            onClick={() => setSortKey(k)}
            className={clsx(
              "px-2 py-0.5 rounded transition-colors",
              sortKey === k
                ? "bg-slate-600 text-slate-200"
                : "text-slate-500 hover:text-slate-300"
            )}
          >
            {l}
          </button>
        ))}
      </div>

      {/* Signal list */}
      <div className="flex-1 overflow-y-auto -mx-1 px-1">
        {loading && (
          <div className="flex items-center justify-center h-32 gap-2 text-slate-400">
            <div className="w-4 h-4 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
            <span className="text-xs">Scanning {scanData?.total_scanned ?? "…"} pairs…</span>
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 text-slate-500 text-xs">
            <span>No signals found</span>
            <span className="mt-1 text-slate-600">Try a different timeframe or lower confidence threshold</span>
          </div>
        )}

        {!loading &&
          filtered.map((sig) => (
            <div
              key={sig.symbol}
              onClick={() => onSelectSymbol(sig.symbol)}
              className={clsx(
                "flex items-center justify-between px-2 py-2.5 rounded-lg mb-1 cursor-pointer transition-all",
                selectedSymbol === sig.symbol
                  ? "bg-brand-blue/20 border border-brand-blue/40"
                  : "hover:bg-surface-2/60 border border-transparent"
              )}
            >
              {/* Left: symbol + direction */}
              <div className="flex items-center gap-2 min-w-0">
                <div>
                  <div className="text-xs font-bold text-slate-200">
                    {sig.symbol.replace("USDT", "")}
                    <span className="text-slate-500 font-normal">/USDT</span>
                  </div>
                  <div className="flex items-center gap-1 mt-0.5">
                    <span className={sig.direction === "LONG" ? "badge-long" : "badge-short"}>
                      {sig.direction === "LONG" ? "▲" : "▼"} {sig.direction}
                    </span>
                  </div>
                </div>
              </div>

              {/* Mid: price + change */}
              <div className="text-right hidden sm:block">
                <div className="text-xs font-mono text-slate-200">
                  ${formatPrice(sig.price)}
                </div>
                <div
                  className={clsx(
                    "text-xs",
                    sig.change_24h >= 0 ? "text-brand-green" : "text-brand-red"
                  )}
                >
                  {formatChange(sig.change_24h)}
                </div>
              </div>

              {/* Right: confidence + AI */}
              <div className="flex flex-col items-end gap-1 ml-2">
                <ConfidenceBar value={sig.confidence} />
                <div className="flex items-center gap-1">
                  <span className="text-xs text-slate-500">AI</span>
                  <AIProbBadge prob={sig.ai_probability} />
                </div>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}
