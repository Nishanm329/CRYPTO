import { formatPrice, confidenceColor, confidenceLabel } from "../lib/api";
import clsx from "clsx";

function MetricBox({ label, value, highlight }) {
  return (
    <div className="bg-surface-2/50 rounded-lg p-2.5">
      <div className="text-xs text-slate-500 mb-0.5">{label}</div>
      <div className={clsx("text-sm font-mono font-semibold", highlight ?? "text-slate-200")}>
        {value}
      </div>
    </div>
  );
}

function ConfidenceMeter({ value }) {
  const color = confidenceColor(value);
  const label = confidenceLabel(value);
  const circumference = 2 * Math.PI * 28;
  const dash = circumference * (value / 100);
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="72" height="72" viewBox="0 0 72 72">
        {/* Track */}
        <circle cx="36" cy="36" r="28" fill="none" stroke="#334155" strokeWidth="6" />
        {/* Fill */}
        <circle
          cx="36" cy="36" r="28"
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          strokeDashoffset={circumference / 4}
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
        <text x="36" y="39" textAnchor="middle" fontSize="14" fontWeight="bold" fill={color} fontFamily="monospace">
          {value}
        </text>
      </svg>
      <span className="text-xs font-medium" style={{ color }}>{label}</span>
    </div>
  );
}

function AIProbGauge({ prob }) {
  const pct = Math.round(prob * 100);
  const color = pct >= 65 ? "#22c55e" : pct >= 50 ? "#f59e0b" : "#ef4444";
  const label = pct >= 65 ? "High" : pct >= 50 ? "Medium" : "Low";
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-16 h-16">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15" fill="none" stroke="#334155" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="15"
            fill="none"
            stroke={color}
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${94.2 * (pct / 100)} 94.2`}
            style={{ transition: "stroke-dasharray 0.6s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-sm font-bold" style={{ color }}>{pct}%</span>
        </div>
      </div>
      <span className="text-xs text-slate-400">AI · {label}</span>
    </div>
  );
}

function IndicatorRow({ ind }) {
  const isPos = ind.status === "BULLISH";
  const isNeg = ind.status === "BEARISH";
  return (
    <div className="flex items-start gap-2 py-2 border-b border-surface-2/50 last:border-0">
      <span
        className={clsx(
          "mt-0.5 text-sm shrink-0",
          isPos ? "text-brand-green" : isNeg ? "text-brand-red" : "text-slate-500"
        )}
      >
        {isPos ? "✓" : isNeg ? "✗" : "·"}
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-300">{ind.name}</span>
          <span
            className={clsx(
              "text-xs font-mono",
              isPos ? "text-brand-green" : isNeg ? "text-brand-red" : "text-slate-500"
            )}
          >
            {ind.value}
          </span>
        </div>
        <div className="text-xs text-slate-500 mt-0.5 truncate">{ind.description}</div>
      </div>
    </div>
  );
}

function TPRow({ tp, entry, isLong }) {
  const pct = Math.abs((tp.price - entry) / entry * 100).toFixed(2);
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-surface-2/30 last:border-0">
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500">TP{tp.level}</span>
        <span className="text-xs font-mono text-brand-green font-medium">
          ${formatPrice(tp.price)}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <span>+{pct}%</span>
        <span className="text-slate-500">{tp.rr_ratio}:1 R:R</span>
      </div>
    </div>
  );
}

export default function SignalCard({ signal, loading }) {
  if (loading) {
    return (
      <div className="card flex items-center justify-center h-48">
        <div className="flex flex-col items-center gap-2">
          <div className="w-6 h-6 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-slate-500">Generating signal…</span>
        </div>
      </div>
    );
  }

  if (!signal) {
    return (
      <div className="card flex items-center justify-center h-48 text-slate-500 text-sm">
        Select a coin from the scanner to view its signal
      </div>
    );
  }

  const isLong = signal.direction === "LONG";
  const dirColor = isLong ? "text-brand-green" : "text-brand-red";
  const dirBg = isLong ? "bg-green-500/10 border-green-500/30" : "bg-red-500/10 border-red-500/30";

  return (
    <div className="card animate-fade-in">
      {/* Signal header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-slate-100">{signal.symbol}</span>
            <span className={clsx("px-2 py-0.5 rounded text-xs font-bold border", dirBg, dirColor)}>
              {isLong ? "▲" : "▼"} {signal.direction}
            </span>
            <span className="text-xs text-slate-500 bg-surface-2 px-2 py-0.5 rounded">
              {signal.timeframe}
            </span>
          </div>
          <div className="text-xs text-slate-500 mt-1">
            EMA 7/25 Cross · {signal.candles_since_cross === 0 ? "Just crossed" : `${signal.candles_since_cross} candle${signal.candles_since_cross !== 1 ? "s" : ""} ago`}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <ConfidenceMeter value={signal.confidence} />
          <AIProbGauge prob={signal.ai_probability} />
        </div>
      </div>

      {/* Price levels */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
        <MetricBox label="Entry" value={`$${formatPrice(signal.entry_price)}`} highlight="text-brand-blue" />
        <MetricBox label="Stop Loss" value={`$${formatPrice(signal.stop_loss)}`} highlight="text-brand-red" />
        <MetricBox label="ATR" value={`$${formatPrice(signal.atr)}`} />
        <MetricBox
          label="R:R Ratio"
          value={`1:${signal.rr_ratio}`}
          highlight={signal.rr_ratio >= 2 ? "text-brand-green" : "text-brand-amber"}
        />
      </div>

      {/* Take profits */}
      <div className="mb-4">
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Take Profits</div>
        <div className="bg-surface-2/30 rounded-lg px-3 py-1">
          {signal.take_profits.map((tp) => (
            <TPRow key={tp.level} tp={tp} entry={signal.entry_price} isLong={isLong} />
          ))}
        </div>
      </div>

      {/* Indicator confirmations */}
      <div>
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
          Indicator Confirmations
        </div>
        <div className="bg-surface-2/30 rounded-lg px-3">
          {signal.indicators.map((ind) => (
            <IndicatorRow key={ind.name} ind={ind} />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-surface-2/50 text-xs text-slate-500">
        <span>Sentiment: <span className={signal.sentiment_score > 0 ? "text-brand-green" : signal.sentiment_score < 0 ? "text-brand-red" : "text-slate-400"}>
          {signal.sentiment_score > 0 ? "+" : ""}{(signal.sentiment_score * 100).toFixed(0)}%
        </span></span>
        <span>Vol ratio: <span className={signal.volume_ratio >= 1.5 ? "text-brand-green" : "text-slate-300"}>{signal.volume_ratio}×</span></span>
        <span className="text-slate-600">{new Date(signal.timestamp).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}
