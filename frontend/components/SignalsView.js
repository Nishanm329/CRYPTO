import { useState } from "react";
import useSWR from "swr";
import { api, formatPrice, formatChange, confidenceColor } from "../lib/api";
import TradeExecutionModal from "./TradeExecutionModal";
import clsx from "clsx";

const TFS = ["1m","5m","15m","1h","4h","1d","3d","1w"];

function SignalCard({ sig, selected, onClick, onExecuteTrade }) {
  const [showTradeModal, setShowTradeModal] = useState(false);
  const isLong = sig.direction === "LONG";
  const confColor = confidenceColor(sig.confidence);

  // Calculate upside and exit point based on RR ratio and confidence
  const riskPercent = 2; // Standard 2% risk per trade
  const rrRatio = sig.rr_ratio || 2;
  const upsidePercent = (riskPercent * rrRatio) * (sig.confidence / 100); // Scale upside by confidence

  const entryPrice = sig.price;
  const upsideTarget = isLong
    ? entryPrice * (1 + upsidePercent / 100)
    : entryPrice * (1 - upsidePercent / 100);

  const exitPrice = isLong
    ? entryPrice * (1 - riskPercent / 100)
    : entryPrice * (1 + riskPercent / 100);

  const upsideGain = ((upsideTarget - entryPrice) / entryPrice) * 100;

  return (
    <div
      onClick={onClick}
      className={clsx(
        "p-3 rounded-xl border cursor-pointer transition-all",
        selected
          ? "bg-brand-blue/10 border-brand-blue/40"
          : "bg-bg-card border-border hover:border-border-light"
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className="text-sm font-bold text-tx">{sig.symbol.replace("USDT","")}</span>
          <span className="text-tx-muted text-xs">/USDT</span>
        </div>
        <span className={clsx(
          "text-xs font-bold px-2 py-0.5 rounded-full",
          isLong ? "bg-brand-green/15 text-brand-green" : "bg-brand-red/15 text-brand-red"
        )}>
          {isLong ? "▲ LONG" : "▼ SHORT"}
        </span>
      </div>

      {/* Entry Price & Change */}
      <div className="text-xs font-mono text-tx mb-2">${formatPrice(sig.price)}
        <span className={clsx("ml-2", sig.change_24h >= 0 ? "text-brand-green" : "text-brand-red")}>
          {formatChange(sig.change_24h)}
        </span>
      </div>

      {/* Confidence Bar */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex-1 mr-3">
          <div className="h-1 bg-bg rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all" style={{ width: `${sig.confidence}%`, backgroundColor: confColor }} />
          </div>
        </div>
        <span className="text-xs font-bold font-mono" style={{ color: confColor }}>{sig.confidence}%</span>
      </div>

      {/* Indicator Tags */}
      <div className="flex flex-wrap gap-1 mb-2">
        {sig.confirmation_indicators && sig.confirmation_indicators.length > 0 ? (
          sig.confirmation_indicators.map((ind) => (
            <span key={ind} className="text-[8px] px-1.5 py-0.5 rounded bg-brand-blue/20 text-brand-blue border border-brand-blue/30">
              {ind}
            </span>
          ))
        ) : (
          <>
            <span className="text-[8px] px-1.5 py-0.5 rounded bg-brand-green/20 text-brand-green border border-brand-green/30">
              RSI
            </span>
            <span className="text-[8px] px-1.5 py-0.5 rounded bg-brand-green/20 text-brand-green border border-brand-green/30">
              MACD
            </span>
            <span className="text-[8px] px-1.5 py-0.5 rounded bg-brand-green/20 text-brand-green border border-brand-green/30">
              BB
            </span>
          </>
        )}
      </div>

      {/* Upside & Exit Points */}
      <div className="grid grid-cols-2 gap-2 mb-2 text-[10px]">
        <div className="bg-bg p-1.5 rounded">
          <div className="text-tx-muted mb-0.5">Upside Target</div>
          <div className="font-mono font-bold text-brand-green">${formatPrice(upsideTarget)}</div>
          <div className="text-brand-green/80 text-[9px]">+{upsideGain.toFixed(1)}%</div>
        </div>
        <div className="bg-bg p-1.5 rounded">
          <div className="text-tx-muted mb-0.5">Exit Point</div>
          <div className="font-mono font-bold text-brand-red">${formatPrice(exitPrice)}</div>
          <div className="text-brand-red/80 text-[9px]">-{riskPercent.toFixed(1)}%</div>
        </div>
      </div>

      {/* AI & Metrics */}
      <div className="flex items-center gap-2 text-[10px] mb-3">
        <span className="text-tx-muted">AI</span>
        <span className="font-bold font-mono" style={{ color: confidenceColor(sig.ai_probability * 100) }}>
          {Math.round(sig.ai_probability * 100)}%
        </span>
        <span className="text-tx-muted ml-auto">R:R {sig.rr_ratio}</span>
        <span className="text-tx-dim">{sig.timeframe.toUpperCase()}</span>
      </div>

      {/* Execute Trade Button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          setShowTradeModal(true);
        }}
        className="w-full py-2 bg-brand-blue hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-all"
      >
        Execute Trade
      </button>

      {/* Trade Execution Modal */}
      <TradeExecutionModal
        signal={showTradeModal ? { ...sig, entry_price: sig.price } : null}
        onClose={() => setShowTradeModal(false)}
        onSuccess={() => {
          setShowTradeModal(false);
          onExecuteTrade && onExecuteTrade(sig);
        }}
      />
    </div>
  );
}

export default function SignalsView({ onSelectSymbol, selectedSymbol }) {
  const [timeframe, setTimeframe] = useState("1h");
  const [filterDir, setFilterDir] = useState("ALL");
  const [sortKey, setSortKey] = useState("confidence");

  // Adaptive scan parameters based on timeframe for optimization
  const getScanParams = (tf) => {
    const params = {
      "1m": { pairs: 150, minConfidence: 50, refresh: 30000 },
      "5m": { pairs: 150, minConfidence: 45, refresh: 45000 },
      "15m": { pairs: 120, minConfidence: 42, refresh: 60000 },
      "1h": { pairs: 100, minConfidence: 40, refresh: 60000 },
      "4h": { pairs: 80, minConfidence: 38, refresh: 300000 },
      "1d": { pairs: 60, minConfidence: 35, refresh: 300000 },
      "3d": { pairs: 50, minConfidence: 35, refresh: 600000 },
      "1w": { pairs: 40, minConfidence: 35, refresh: 600000 },
    };
    return params[tf] || params["1h"];
  };

  const scanParams = getScanParams(timeframe);

  const { data: scanData, isLoading, mutate } = useSWR(
    `scan-signals-${timeframe}`,
    () => api.scan(timeframe, scanParams.pairs, scanParams.minConfidence),
    { refreshInterval: scanParams.refresh, revalidateOnFocus: false, dedupingInterval: 30000 }
  );

  const signals = (scanData?.signals ?? [])
    .filter(s => filterDir === "ALL" || s.direction === filterDir)
    .sort((a, b) => {
      if (sortKey === "confidence") return b.confidence - a.confidence;
      if (sortKey === "ai") return b.ai_probability - a.ai_probability;
      if (sortKey === "rr") return b.rr_ratio - a.rr_ratio;
      return 0;
    });

  const longCount = scanData?.long_count ?? 0;
  const shortCount = scanData?.short_count ?? 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 border-b border-border px-5 py-3 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse" />
          <span className="text-sm font-bold text-tx">Live Signals</span>
          {scanData && (
            <span className="text-xs text-tx-muted">{scanData.total_scanned} pairs scanned · {scanData.scan_duration_ms}ms</span>
          )}
        </div>

        {/* Summary badges */}
        {scanData && (
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-brand-green/15 text-brand-green">▲ {longCount} Long</span>
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-brand-red/15 text-brand-red">▼ {shortCount} Short</span>
          </div>
        )}

        <div className="flex items-center gap-1 ml-auto">
          {/* Direction filter */}
          {["ALL","LONG","SHORT"].map(d => (
            <button key={d} onClick={() => setFilterDir(d)}
              className={clsx("px-2.5 py-1 rounded-lg text-xs font-semibold transition-all",
                filterDir === d ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
              )}
            >{d}</button>
          ))}
          <div className="w-px h-4 bg-border mx-1" />
          {/* Sort */}
          {[["confidence","Conf"],["ai","AI"],["rr","R:R"]].map(([k,l]) => (
            <button key={k} onClick={() => setSortKey(k)}
              className={clsx("px-2.5 py-1 rounded-lg text-xs transition-all",
                sortKey === k ? "bg-border text-tx" : "text-tx-muted hover:text-tx"
              )}
            >{l}</button>
          ))}
          <div className="w-px h-4 bg-border mx-1" />
          {/* Timeframe */}
          {TFS.map(tf => (
            <button key={tf} onClick={() => setTimeframe(tf)}
              className={clsx("px-2 py-1 rounded text-xs font-semibold transition-all",
                timeframe === tf ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
              )}
            >{tf.toUpperCase()}</button>
          ))}
          <button onClick={() => mutate()} className="ml-2 p-1.5 rounded-lg text-tx-muted hover:text-tx hover:bg-border transition-all">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-4">
        {isLoading && (
          <div className="flex items-center justify-center h-48 gap-2 text-tx-muted">
            <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Scanning market…</span>
          </div>
        )}
        {!isLoading && signals.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 text-tx-muted">
            <span className="text-sm">No signals found</span>
            <span className="text-xs mt-1">Try a different timeframe</span>
          </div>
        )}
        {!isLoading && (
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {signals.map(sig => (
              <SignalCard
                key={sig.symbol}
                sig={sig}
                selected={selectedSymbol === sig.symbol}
                onClick={() => onSelectSymbol?.(sig.symbol)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
