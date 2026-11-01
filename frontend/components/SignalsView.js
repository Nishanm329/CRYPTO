import { useState, useEffect, useRef } from "react";
import useSWR from "swr";
import { api, formatPrice, formatChange, confidenceColor } from "../lib/api";
import TradeExecutionModal from "./TradeExecutionModal";
import EmailScheduleButton from "./EmailScheduleButton";
import clsx from "clsx";

const TFS = ["1m","5m","15m","1h","4h","1d","3d","1w"];
const PRECROSS_TFS = ["1d", "3d", "1w"];
const PRECROSS_THRESHOLDS = [2, 5, 10, 15];

function PreCrossCard({ alert, selected, onClick }) {
  const isLong = alert.direction === "LONG";
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
          <span className="text-sm font-bold text-tx">{alert.symbol.replace("USDT", "")}</span>
          <span className="text-tx-muted text-xs">/USDT</span>
        </div>
        <span className={clsx(
          "text-xs font-bold px-2 py-0.5 rounded-full",
          isLong ? "bg-brand-green/15 text-brand-green" : "bg-brand-red/15 text-brand-red"
        )}>
          {isLong ? "▲ Converging Up" : "▼ Converging Down"}
        </span>
      </div>

      <div className="text-xs font-mono text-tx mb-2">${formatPrice(alert.price)}
        <span className={clsx("ml-2", alert.change_24h >= 0 ? "text-brand-green" : "text-brand-red")}>
          {formatChange(alert.change_24h)}
        </span>
      </div>

      {/* EMA gap distance to threshold */}
      <div className="mb-2">
        <div className="flex items-center justify-between text-[10px] text-tx-muted mb-1">
          <span>EMA 7/25 gap</span>
          <span className="font-mono font-bold text-tx">{alert.spread_pct}%</span>
        </div>
        <div className="h-1 bg-bg rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-brand-amber transition-all"
            style={{ width: `${Math.max(4, 100 - (alert.spread_pct / alert.threshold_pct) * 100)}%` }}
          />
        </div>
      </div>

      <div className="flex items-center gap-2 text-[10px]">
        <span className="text-tx-muted">Threshold {alert.threshold_pct}%</span>
        <span className="text-tx-dim ml-auto">{alert.timeframe.toUpperCase()}</span>
      </div>
    </div>
  );
}

function DivergenceCard({ alert, selected, onClick }) {
  const isLong = alert.direction === "LONG";
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
          <span className="text-sm font-bold text-tx">{alert.symbol.replace("USDT", "")}</span>
          <span className="text-tx-muted text-xs">/USDT</span>
        </div>
        <span className={clsx(
          "text-xs font-bold px-2 py-0.5 rounded-full",
          isLong ? "bg-brand-green/15 text-brand-green" : "bg-brand-red/15 text-brand-red"
        )}>
          {isLong ? "▲ Bullish Div" : "▼ Bearish Div"}
        </span>
      </div>

      <div className="text-xs font-mono text-tx mb-2">${formatPrice(alert.price)}
        <span className={clsx("ml-2", alert.change_24h >= 0 ? "text-brand-green" : "text-brand-red")}>
          {formatChange(alert.change_24h)}
        </span>
      </div>

      <div className="text-[11px] text-tx-muted mb-2">{alert.description}</div>

      <div className="flex items-center gap-2 text-[10px]">
        <span className="text-tx-muted">RSI {alert.rsi}</span>
        <span className="text-tx-dim ml-auto">{alert.timeframe.toUpperCase()}</span>
      </div>
    </div>
  );
}

function SignalCard({ sig, rank, selected, onClick, onExecuteTrade, quote = "USDT", simple = false }) {
  const [showTradeModal, setShowTradeModal] = useState(false);
  const isLong = sig.direction === "LONG";
  const confColor = confidenceColor(sig.confidence);
  const priceSymbol = quote === "BTC" ? "₿" : "$";

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

  if (simple) {
    return (
      <div
        onClick={onClick}
        className={clsx(
          "flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all",
          selected ? "bg-brand-blue/10 border-brand-blue/40" : "bg-bg-card border-border hover:border-border-light"
        )}
      >
        {rank != null && (
          <span className={clsx("text-[10px] font-bold font-mono w-6 text-center shrink-0",
            rank === 1 ? "text-brand-amber" : "text-tx-muted")}>#{rank}</span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-tx">{sig.symbol.replace(quote, "")}</span>
            <span className="text-tx-muted text-xs">/{quote}</span>
            <span className={clsx("text-[10px] font-bold px-1.5 py-0.5 rounded-full",
              isLong ? "bg-brand-green/15 text-brand-green" : "bg-brand-red/15 text-brand-red")}>
              {isLong ? "▲ LONG" : "▼ SHORT"}
            </span>
          </div>
          <div className="text-[11px] font-mono text-tx-muted mt-0.5 truncate">
            {priceSymbol}{formatPrice(sig.price)} · Target {priceSymbol}{formatPrice(upsideTarget)} · Stop {priceSymbol}{formatPrice(exitPrice)}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-lg font-bold font-mono leading-none" style={{ color: confColor }}>{sig.confidence}%</div>
          <div className="text-[10px] text-tx-dim mt-1">{sig.timeframe.toUpperCase()}</div>
        </div>
      </div>
    );
  }

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
        <div className="flex items-center gap-1.5">
          {rank != null && (
            <span
              className={clsx(
                "text-[10px] font-bold font-mono px-1.5 py-0.5 rounded shrink-0",
                rank === 1 ? "bg-brand-amber/20 text-brand-amber" : "bg-bg text-tx-muted"
              )}
            >
              #{rank}
            </span>
          )}
          <span className="text-sm font-bold text-tx">{sig.symbol.replace(quote,"")}</span>
          <span className="text-tx-muted text-xs">/{quote}</span>
        </div>
        <span className={clsx(
          "text-xs font-bold px-2 py-0.5 rounded-full",
          isLong ? "bg-brand-green/15 text-brand-green" : "bg-brand-red/15 text-brand-red"
        )}>
          {isLong ? "▲ LONG" : "▼ SHORT"}
        </span>
      </div>

      {/* Entry Price & Change */}
      <div className="text-xs font-mono text-tx mb-2">{priceSymbol}{formatPrice(sig.price)}
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
          <div className="text-tx-muted mb-0.5">{isLong ? "Upside Target" : "Downside Target"}</div>
          <div className="font-mono font-bold text-brand-green">{priceSymbol}{formatPrice(upsideTarget)}</div>
          <div className="text-brand-green/80 text-[9px]">{upsideGain >= 0 ? "+" : ""}{upsideGain.toFixed(1)}%</div>
        </div>
        <div className="bg-bg p-1.5 rounded">
          <div className="text-tx-muted mb-0.5">Exit Point</div>
          <div className="font-mono font-bold text-brand-red">{priceSymbol}{formatPrice(exitPrice)}</div>
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

      {/* Start Paper Bot — the bot engine sizes positions in USDT, which
          doesn't map onto a BTC-quoted pair, so this stays informational-only
          for quote !== "USDT" rather than pretending to execute correctly. */}
      {quote === "USDT" ? (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowTradeModal(true);
          }}
          className="w-full py-2 bg-brand-blue hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-all"
        >
          Start Paper Bot
        </button>
      ) : (
        <div className="w-full py-2 text-center text-tx-dim text-[10px]">
          Informational — vs BTC, not tradable as a paper bot
        </div>
      )}

      {/* Trade Execution Modal — only mounted while actually open, so idle
          signal cards don't each fire a getKeysStatus() network call */}
      {showTradeModal && (
        <TradeExecutionModal
          signal={{ ...sig, entry_price: sig.price }}
          onClose={() => setShowTradeModal(false)}
          onSuccess={() => {
            setShowTradeModal(false);
            onExecuteTrade && onExecuteTrade(sig);
          }}
        />
      )}
    </div>
  );
}

export default function SignalsView({ onSelectSymbol, selectedSymbol, variant = "signals", lite = false }) {
  const isScanner = variant === "scanner";
  const [timeframe, setTimeframe] = useState("1d");
  const [filterDir, setFilterDir] = useState("ALL");
  const [sortKey, setSortKey] = useState("confidence");
  // Scanner lets the user set their own confidence floor; null = adaptive default.
  const [minConf, setMinConf] = useState(null);
  // Pre-cross (EMA convergence) mode — scanner-only alt signal type.
  const [precrossMode, setPrecrossMode] = useState(false);
  const [precrossThreshold, setPrecrossThreshold] = useState(5);
  const seenPrecrossRef = useRef(new Set());
  // Divergence mode — standalone RSI/price divergence alerts, independent of any EMA cross.
  const [divergenceMode, setDivergenceMode] = useState(false);
  const seenDivergenceRef = useRef(new Set());
  // BTC mode — same signal engine, run against BTC-quoted pairs (e.g. ETHBTC)
  // instead of USDT pairs, i.e. altcoin strength vs BTC rather than vs the
  // dollar. Binance only lists ~38 such pairs total (not the 100 of the
  // USDT universe), so this is a smaller, liquidity-ranked list by nature.
  const [btcMode, setBtcMode] = useState(false);
  const [toasts, setToasts] = useState([]);
  // Simple view (default): a stripped-down header and one-line cards. Detailed
  // is the original full-control layout. Read from localStorage post-mount so
  // SSR and first client render agree.
  const [simple, setSimple] = useState(true);
  useEffect(() => {
    if (lite) return;
    try { if (localStorage.getItem("signalsViewMode") === "detailed") setSimple(false); } catch {}
  }, []);
  const setViewMode = (isSimple) => {
    setSimple(isSimple);
    try { localStorage.setItem("signalsViewMode", isSimple ? "simple" : "detailed"); } catch {}
  };

  const togglePrecross = () => {
    setPrecrossMode((on) => {
      const next = !on;
      if (next) {
        setDivergenceMode(false);
        setBtcMode(false);
        if (!PRECROSS_TFS.includes(timeframe)) setTimeframe("1d");
      }
      return next;
    });
  };

  const toggleDivergence = () => {
    setDivergenceMode((on) => {
      const next = !on;
      if (next) {
        setPrecrossMode(false);
        setBtcMode(false);
      }
      return next;
    });
  };

  const toggleBtc = () => {
    setBtcMode((on) => {
      const next = !on;
      if (next) {
        setPrecrossMode(false);
        setDivergenceMode(false);
      }
      return next;
    });
  };

  // Adaptive scan parameters based on timeframe for optimization
  const getScanParams = (tf) => {
    const params = {
      // Scans 100 pairs. The backend pre-computes the full scan in the background
      // (default 1h) and serves any confidence filter from one cached result, so
      // the request returns instantly. A cold cache returns a `warming` flag and
      // we poll quickly (below) until the background scan completes.
      "1m": { pairs: 100, minConfidence: 50, refresh: 30000 },
      "5m": { pairs: 100, minConfidence: 45, refresh: 45000 },
      "15m": { pairs: 100, minConfidence: 42, refresh: 60000 },
      "1h": { pairs: 100, minConfidence: 40, refresh: 60000 },
      "4h": { pairs: 100, minConfidence: 38, refresh: 300000 },
      "1d": { pairs: 100, minConfidence: 35, refresh: 300000 },
      "3d": { pairs: 100, minConfidence: 35, refresh: 600000 },
      "1w": { pairs: 100, minConfidence: 35, refresh: 600000 },
    };
    return params[tf] || params["1h"];
  };

  const scanParams = getScanParams(timeframe);
  const effectiveMinConf = isScanner && minConf != null ? minConf : scanParams.minConfidence;

  const { data: scanData, isLoading, mutate } = useSWR(
    `scan-${variant}-${timeframe}-${effectiveMinConf}`,
    () => api.scan(timeframe, scanParams.pairs, effectiveMinConf),
    {
      // While the backend is still computing a cold scan, poll fast so results
      // appear within seconds instead of waiting a full refresh interval.
      refreshInterval: (latest) => (latest?.warming ? 4000 : scanParams.refresh),
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  const warming = scanData?.warming === true;

  const { data: precrossData, isLoading: precrossLoading } = useSWR(
    isScanner && precrossMode ? `precross-${timeframe}-${precrossThreshold}` : null,
    () => api.scanPrecross(timeframe, 100, precrossThreshold),
    {
      // Poll fast while the backend's cache is cold (warming), like the main scan.
      refreshInterval: (latest) => (latest?.warming ? 4000 : 60000),
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );
  const precrossAlerts = precrossData?.alerts ?? [];
  const precrossWarming = precrossData?.warming === true;

  const { data: divergenceData, isLoading: divergenceLoading } = useSWR(
    isScanner && divergenceMode ? `divergence-${timeframe}` : null,
    () => api.scanDivergence(timeframe, 100),
    {
      refreshInterval: (latest) => (latest?.warming ? 4000 : 60000),
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );
  const divergenceAlerts = divergenceData?.alerts ?? [];
  const divergenceWarming = divergenceData?.warming === true;

  const { data: btcData, isLoading: btcLoading } = useSWR(
    isScanner && btcMode ? `scan-btc-${timeframe}-${effectiveMinConf}` : null,
    () => api.scanBtc(timeframe, 100, effectiveMinConf),
    {
      refreshInterval: (latest) => (latest?.warming ? 4000 : scanParams.refresh),
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );
  const btcWarming = btcData?.warming === true;
  const btcSignals = (btcData?.signals ?? [])
    .filter(s => s.confidence >= 65)
    .filter(s => filterDir === "ALL" || s.direction === filterDir)
    .sort((a, b) => {
      if (sortKey === "confidence") return b.confidence - a.confidence;
      if (sortKey === "ai") return b.ai_probability - a.ai_probability;
      if (sortKey === "rr") return b.rr_ratio - a.rr_ratio;
      return 0;
    });

  // Fire a toast + browser notification the first time a symbol appears in the
  // pre-cross list (new convergence detected), matching AlertMonitor's pattern.
  useEffect(() => {
    if (!isScanner || !precrossMode || precrossAlerts.length === 0) return;
    const seen = seenPrecrossRef.current;
    const fresh = precrossAlerts.filter((a) => !seen.has(`${a.symbol}-${a.timeframe}`));
    if (fresh.length === 0) return;
    fresh.forEach((a) => seen.add(`${a.symbol}-${a.timeframe}`));

    fresh.forEach((a) => {
      const name = a.symbol.replace("USDT", "");
      const dir = a.direction === "LONG" ? "bullish" : "bearish";
      const message = `${name} EMA 7/25 converging (${dir}) — ${a.spread_pct}% apart on ${a.timeframe.toUpperCase()}`;
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        try { new Notification("EMA pre-cross", { body: message, tag: `precross-${a.symbol}-${a.timeframe}` }); } catch {}
      }
      const id = `${a.symbol}-${a.timeframe}-${Date.now()}`;
      setToasts((t) => [...t, { id, message }]);
      setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 9000);
    });
  }, [isScanner, precrossMode, precrossAlerts]);

  // Fire a toast + browser notification the first time a symbol appears in the
  // divergence list (fresh RSI/price divergence detected).
  useEffect(() => {
    if (!isScanner || !divergenceMode || divergenceAlerts.length === 0) return;
    const seen = seenDivergenceRef.current;
    const fresh = divergenceAlerts.filter((a) => !seen.has(`${a.symbol}-${a.timeframe}`));
    if (fresh.length === 0) return;
    fresh.forEach((a) => seen.add(`${a.symbol}-${a.timeframe}`));

    fresh.forEach((a) => {
      const name = a.symbol.replace("USDT", "");
      const dir = a.direction === "LONG" ? "bullish" : "bearish";
      const message = `${name} ${dir} RSI divergence on ${a.timeframe.toUpperCase()} — ${a.description}`;
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        try { new Notification("RSI divergence", { body: message, tag: `divergence-${a.symbol}-${a.timeframe}` }); } catch {}
      }
      const id = `${a.symbol}-${a.timeframe}-${Date.now()}`;
      setToasts((t) => [...t, { id, message }]);
      setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 9000);
    });
  }, [isScanner, divergenceMode, divergenceAlerts]);

  const signals = (scanData?.signals ?? [])
    .filter(s => s.confidence >= 65)
    .filter(s => filterDir === "ALL" || s.direction === filterDir)
    .sort((a, b) => {
      if (sortKey === "confidence") return b.confidence - a.confidence;
      if (sortKey === "ai") return b.ai_probability - a.ai_probability;
      if (sortKey === "rr") return b.rr_ratio - a.rr_ratio;
      return 0;
    });

  const filteredPrecrossAlerts = precrossAlerts
    .filter(a => filterDir === "ALL" || a.direction === filterDir)
    .sort((a, b) => a.spread_pct - b.spread_pct);

  const filteredDivergenceAlerts = divergenceAlerts
    .filter(a => filterDir === "ALL" || a.direction === filterDir);

  // btcData carries its own long_count/short_count (same MarketScanResponse
  // shape as the main scan); precross/divergence alerts don't, so those modes
  // fall back to the main scan's counts as before.
  const longCount = (btcMode ? btcData?.long_count : scanData?.long_count) ?? 0;
  const shortCount = (btcMode ? btcData?.short_count : scanData?.short_count) ?? 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Simple header: title, one type row (scanner), direction, 4 timeframes */}
      {simple && (
        <div className="shrink-0 border-b border-border px-4 py-3 space-y-2.5">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse" />
            <span className="text-sm font-bold text-tx">{isScanner ? "Market Scanner" : "Live Signals"}</span>
            <div className="ml-auto flex items-center gap-2">
              <EmailScheduleButton component={isScanner ? "scanner" : "signals"} />
              {!lite && (
                <button onClick={() => setViewMode(false)}
                  className="text-[11px] text-tx-muted hover:text-tx underline underline-offset-2">
                  Detailed view
                </button>
              )}
            </div>
          </div>
          {isScanner && (
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
              {[
                ["Signals", !precrossMode && !divergenceMode && !btcMode, () => { setPrecrossMode(false); setDivergenceMode(false); setBtcMode(false); }],
                ["Near cross", precrossMode, () => { if (!precrossMode) togglePrecross(); }],
                ["Divergence", divergenceMode, () => { if (!divergenceMode) toggleDivergence(); }],
                ["vs BTC", btcMode, () => { if (!btcMode) toggleBtc(); }],
              ].map(([label, active, onPick]) => (
                <button key={label} onClick={onPick}
                  className={clsx("shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                    active ? "bg-brand-blue text-white" : "bg-bg-card/60 text-tx-muted hover:text-tx")}
                >{label}</button>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1">
              {["ALL", "LONG", "SHORT"].map(d => (
                <button key={d} onClick={() => setFilterDir(d)}
                  className={clsx("px-2.5 py-1 rounded-lg text-xs font-semibold transition-all",
                    filterDir === d ? "bg-border text-tx" : "text-tx-muted hover:text-tx")}
                >{d}</button>
              ))}
            </div>
            <div className="flex items-center gap-1 ml-auto">
              {(precrossMode ? PRECROSS_TFS : ["1h", "4h", "1d", "1w"]).map(tf => (
                <button key={tf} onClick={() => setTimeframe(tf)}
                  className={clsx("min-w-[40px] px-2.5 py-1 rounded-lg text-xs font-semibold transition-all",
                    timeframe === tf ? "bg-brand-blue text-white" : "bg-bg-card/60 text-tx-muted hover:text-tx")}
                >{tf.toUpperCase()}</button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      {!simple && (
      <div className="shrink-0 border-b border-border px-5 py-3 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse" />
          <span className="text-sm font-bold text-tx">{isScanner ? "Market Scanner" : "Live Signals"}</span>
          {btcMode ? (
            btcData && (
              <span className="text-xs text-tx-muted">{btcData.total_scanned} BTC pairs scanned · {btcData.scan_duration_ms}ms</span>
            )
          ) : (
            scanData && (
              <span className="text-xs text-tx-muted">{scanData.total_scanned} pairs scanned · {scanData.scan_duration_ms}ms</span>
            )
          )}
        </div>

        {/* Scanner-only: pre-cross (EMA convergence) mode toggle */}
        {isScanner && (
          <button onClick={togglePrecross}
            className={clsx("px-2.5 py-1 rounded-lg text-xs font-semibold transition-all",
              precrossMode ? "bg-brand-amber text-black" : "bg-bg-card/60 text-tx-muted hover:text-tx"
            )}
          >⚡ Pre-Cross</button>
        )}

        {/* Scanner-only: standalone RSI/price divergence mode toggle */}
        {isScanner && (
          <button onClick={toggleDivergence}
            className={clsx("px-2.5 py-1 rounded-lg text-xs font-semibold transition-all",
              divergenceMode ? "bg-brand-purple text-white" : "bg-bg-card/60 text-tx-muted hover:text-tx"
            )}
          >↕ Divergence</button>
        )}

        {/* Scanner-only: same signal engine run against BTC-quoted pairs instead
            of USDT — altcoin strength vs BTC rather than vs the dollar. */}
        {isScanner && (
          <button onClick={toggleBtc} title="Signals for the top BTC-quoted pairs (e.g. ETHBTC), not USDT"
            className={clsx("px-2.5 py-1 rounded-lg text-xs font-semibold transition-all",
              btcMode ? "bg-brand-gold text-black" : "bg-bg-card/60 text-tx-muted hover:text-tx"
            )}
          >₿ vs BTC</button>
        )}

        {/* Scanner-only: user-controlled minimum confidence threshold (signals mode) */}
        {isScanner && !precrossMode && !divergenceMode && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-tx-muted">Min Conf</span>
            {[null, 40, 55, 70, 85].map((c) => (
              <button key={c ?? "auto"} onClick={() => setMinConf(c)}
                className={clsx("px-2 py-1 rounded-lg text-xs font-semibold transition-all",
                  (minConf === c) ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
                )}
              >{c == null ? "Auto" : `${c}%`}</button>
            ))}
          </div>
        )}

        {/* Scanner-only: user-selectable convergence threshold (pre-cross mode) */}
        {isScanner && precrossMode && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-tx-muted">Gap ≤</span>
            {PRECROSS_THRESHOLDS.map((t) => (
              <button key={t} onClick={() => setPrecrossThreshold(t)}
                className={clsx("px-2 py-1 rounded-lg text-xs font-semibold transition-all",
                  (precrossThreshold === t) ? "bg-brand-amber text-black" : "text-tx-muted hover:text-tx"
                )}
              >{t}%</button>
            ))}
          </div>
        )}

        {/* Summary badges */}
        {!precrossMode && !divergenceMode && scanData && (
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-brand-green/15 text-brand-green">▲ {longCount} Long</span>
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-brand-red/15 text-brand-red">▼ {shortCount} Short</span>
          </div>
        )}
        {precrossMode && precrossData && (
          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-brand-amber/15 text-brand-amber">{filteredPrecrossAlerts.length} converging</span>
        )}
        {divergenceMode && divergenceData && (
          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-brand-purple/15 text-brand-purple">{filteredDivergenceAlerts.length} diverging</span>
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
          <button onClick={() => mutate()} className="ml-2 p-1.5 rounded-lg text-tx-muted hover:text-tx hover:bg-border transition-all">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
            </svg>
          </button>
          <EmailScheduleButton component={isScanner ? "scanner" : "signals"} />
          <EmailScheduleButton component="top-calls" label="Top Calls digest (1D/3D/1W)" />
          <button onClick={() => setViewMode(true)}
            className="ml-2 text-[11px] text-tx-muted hover:text-tx underline underline-offset-2">
            Simple view
          </button>
        </div>

        {/* Timeframe — own full-width scrollable row on mobile so the 8 buttons
            are reachable and tappable; stays inline & compact on desktop. */}
        <div
          className="w-full md:w-auto flex items-center gap-1.5 overflow-x-auto no-scrollbar -mx-1 px-1 md:mx-0 md:px-0 md:ml-2
            [mask-image:linear-gradient(to_right,black_92%,transparent_100%)]
            [-webkit-mask-image:linear-gradient(to_right,black_92%,transparent_100%)]
            md:[mask-image:none] md:[-webkit-mask-image:none]"
        >
          {(precrossMode ? PRECROSS_TFS : TFS).map(tf => (
            <button key={tf} onClick={() => setTimeframe(tf)}
              className={clsx("shrink-0 min-w-[46px] px-3 py-2 md:py-1 rounded-lg text-xs font-semibold transition-all",
                timeframe === tf ? "bg-brand-blue text-white" : "bg-bg-card/60 text-tx-muted hover:text-tx active:bg-border"
              )}
            >{tf.toUpperCase()}</button>
          ))}
        </div>
      </div>
      )}

      {/* Grid */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-4">
        {btcMode ? (
          <>
            {(btcLoading || btcWarming) && (
              <div className="flex items-center justify-center h-48 gap-2 text-tx-muted">
                <div className="w-5 h-5 border-2 border-brand-gold border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">{btcWarming ? "Scanning BTC-quoted pairs…" : "Scanning vs BTC…"}</span>
              </div>
            )}
            {!btcLoading && !btcWarming && btcSignals.length === 0 && (
              <div className="flex flex-col items-center justify-center h-48 text-tx-muted">
                <span className="text-sm">No signals found</span>
                <span className="text-xs mt-1">Try a different timeframe — only ~38 BTC-quoted pairs exist on Binance</span>
              </div>
            )}
            {!btcLoading && !btcWarming && (
              <div className={simple ? "grid grid-cols-1 gap-2 max-w-2xl mx-auto" : "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3"}>
                {btcSignals.map((sig, idx) => (
                  <SignalCard
                    key={sig.symbol}
                    sig={sig}
                    rank={idx + 1}
                    quote="BTC"
                    simple={simple}
                    selected={selectedSymbol === sig.symbol}
                    onClick={() => onSelectSymbol?.(sig.symbol)}
                  />
                ))}
              </div>
            )}
          </>
        ) : divergenceMode ? (
          <>
            {(divergenceLoading || divergenceWarming) && (
              <div className="flex items-center justify-center h-48 gap-2 text-tx-muted">
                <div className="w-5 h-5 border-2 border-brand-purple border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">{divergenceWarming ? "Scanning top 100 pairs…" : "Scanning for divergence…"}</span>
              </div>
            )}
            {!divergenceLoading && !divergenceWarming && filteredDivergenceAlerts.length === 0 && (
              <div className="flex flex-col items-center justify-center h-48 text-tx-muted">
                <span className="text-sm">No divergence found</span>
                <span className="text-xs mt-1">Try a different timeframe</span>
              </div>
            )}
            {!divergenceLoading && !divergenceWarming && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {filteredDivergenceAlerts.map(alert => (
                  <DivergenceCard
                    key={`${alert.symbol}-${alert.timeframe}`}
                    alert={alert}
                    selected={selectedSymbol === alert.symbol}
                    onClick={() => onSelectSymbol?.(alert.symbol)}
                  />
                ))}
              </div>
            )}
          </>
        ) : precrossMode ? (
          <>
            {(precrossLoading || precrossWarming) && (
              <div className="flex items-center justify-center h-48 gap-2 text-tx-muted">
                <div className="w-5 h-5 border-2 border-brand-amber border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">{precrossWarming ? "Scanning top 100 pairs…" : "Scanning for convergence…"}</span>
              </div>
            )}
            {!precrossLoading && !precrossWarming && filteredPrecrossAlerts.length === 0 && (
              <div className="flex flex-col items-center justify-center h-48 text-tx-muted">
                <span className="text-sm">No converging pairs found</span>
                <span className="text-xs mt-1">Try a wider gap threshold or different timeframe</span>
              </div>
            )}
            {!precrossLoading && !precrossWarming && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {filteredPrecrossAlerts.map(alert => (
                  <PreCrossCard
                    key={`${alert.symbol}-${alert.timeframe}`}
                    alert={alert}
                    selected={selectedSymbol === alert.symbol}
                    onClick={() => onSelectSymbol?.(alert.symbol)}
                  />
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            {(isLoading || warming) && (
              <div className="flex items-center justify-center h-48 gap-2 text-tx-muted">
                <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">{warming ? "Scanning top 100 pairs…" : "Scanning market…"}</span>
              </div>
            )}
            {!isLoading && !warming && signals.length === 0 && (
              <div className="flex flex-col items-center justify-center h-48 text-tx-muted">
                <span className="text-sm">No signals found</span>
                <span className="text-xs mt-1">Try a different timeframe</span>
              </div>
            )}
            {!isLoading && !warming && (
              <div className={simple ? "grid grid-cols-1 gap-2 max-w-2xl mx-auto" : "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3"}>
                {signals.map((sig, idx) => (
                  <SignalCard
                    key={sig.symbol}
                    sig={sig}
                    rank={idx + 1}
                    simple={simple}
                    selected={selectedSymbol === sig.symbol}
                    onClick={() => onSelectSymbol?.(sig.symbol)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Pre-cross alert toasts */}
      {toasts.length > 0 && (
        <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 z-[60] flex flex-col gap-2">
          {toasts.map((t) => (
            <div
              key={t.id}
              className="bg-bg-card border border-brand-amber/40 rounded-lg p-3 shadow-lg flex items-start gap-2 animate-in fade-in slide-in-from-bottom-2 duration-300"
            >
              <span className="text-brand-amber shrink-0">⚡</span>
              <span className="text-xs font-medium text-tx flex-1">{t.message}</span>
              <button
                onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}
                className="text-tx-muted hover:text-tx transition-colors shrink-0"
                aria-label="Dismiss"
              >
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
