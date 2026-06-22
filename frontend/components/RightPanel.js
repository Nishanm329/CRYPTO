import clsx from "clsx";
import { formatPrice } from "../lib/api";

// ── Signal Card ─────────────────────────────────────────────────────────────

function SignalRow({ label, value, color }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/60 last:border-0">
      <span className="text-xs text-tx-muted">{label}</span>
      <span className={clsx("text-sm font-mono font-semibold", color ?? "text-tx")}>
        {value}
      </span>
    </div>
  );
}

function SignalCard({ signal, loading }) {
  if (loading) {
    return (
      <div className="card flex items-center justify-center h-56">
        <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!signal) {
    return (
      <div className="card flex items-center justify-center h-48 text-tx-muted text-xs text-center px-4">
        Select a coin to view its signal
      </div>
    );
  }

  const isLong = signal.direction === "LONG";
  const conf = signal.confidence;
  const confColor = conf >= 75 ? "#00c896" : conf >= 55 ? "#f59e0b" : "#ef4444";

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-semibold text-tx-muted">Signal</span>
        <div className="flex items-center gap-2">
          <span className={clsx("text-xl font-bold", isLong ? "text-brand-green" : "text-brand-red")}>
            {isLong ? "BUY" : "SELL"}
          </span>
          <span className={clsx("text-lg", isLong ? "text-brand-green" : "text-brand-red")}>
            {isLong ? "↗" : "↙"}
          </span>
        </div>
      </div>

      {/* Confidence */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-tx-muted">Confidence</span>
          <span className="text-xs font-bold font-mono" style={{ color: confColor }}>{conf}%</span>
        </div>
        <div className="h-2 bg-border rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${conf}%`, background: confColor }}
          />
        </div>
      </div>

      {/* Price levels */}
      <div className="space-y-0">
        <SignalRow label="Entry" value={`${formatPrice(signal.entry_price)}`} color="text-tx" />
        <SignalRow label="Stop Loss" value={`${formatPrice(signal.stop_loss)}`} color="text-brand-red" />
        <SignalRow
          label="Take Profit 1"
          value={`${formatPrice(signal.take_profits?.[0]?.price)}`}
          color="text-brand-green"
        />
        <SignalRow
          label="Take Profit 2"
          value={`${formatPrice(signal.take_profits?.[1]?.price)}`}
          color="text-brand-green"
        />
        <SignalRow
          label="Risk / Reward"
          value={`1 : ${signal.rr_ratio}`}
          color={signal.rr_ratio >= 2 ? "text-brand-green" : "text-brand-amber"}
        />
        <SignalRow
          label="Position Size"
          value={`${signal.volume_ratio?.toFixed(2) ?? "—"} units`}
        />
      </div>
      <div className="text-xs text-tx-muted mt-2 italic">Based on 1% risk</div>

      {/* Indicator confirmations */}
      {signal.indicators?.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border/60">
          <div className="text-xs text-tx-muted uppercase tracking-wider mb-2">
            Indicator Confirmations
          </div>
          <div className="space-y-0">
            {signal.indicators.map((ind) => (
              <IndicatorRow key={ind.name} ind={ind} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function IndicatorRow({ ind }) {
  const isPos = ind.status === "BULLISH";
  const isNeg = ind.status === "BEARISH";
  const color = isPos ? "text-brand-green" : isNeg ? "text-brand-red" : "text-tx-muted";
  return (
    <div className="flex items-start gap-2 py-2 border-b border-border/60 last:border-0">
      <span className={clsx("mt-0.5 text-sm shrink-0", color)}>
        {isPos ? "✓" : isNeg ? "✗" : "·"}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-tx">{ind.name}</span>
          <span className={clsx("text-xs font-mono shrink-0", color)}>{ind.value}</span>
        </div>
        {ind.description && (
          <div className="text-xs text-tx-muted mt-0.5 leading-snug">{ind.description}</div>
        )}
      </div>
    </div>
  );
}

// ── Sentiment Gauge ──────────────────────────────────────────────────────────

function ArcGauge({ value = 50, size = 120 }) {
  const color =
    value >= 75 ? "#00c896" :
    value >= 55 ? "#86efac" :
    value >= 45 ? "#f59e0b" :
    value >= 25 ? "#f97316" :
    "#ef4444";

  const R = size / 2 - 8;
  const cx = size / 2, cy = size / 2;
  const angle = Math.PI + (value / 100) * Math.PI;
  const x = cx + R * Math.cos(angle);
  const y = cy + R * Math.sin(angle);

  const zones = [
    [0, 25, "#ef4444"], [25, 45, "#f97316"], [45, 55, "#f59e0b"],
    [55, 75, "#86efac"], [75, 100, "#00c896"],
  ];

  return (
    <svg width={size} height={size / 2 + 10} viewBox={`0 0 ${size} ${size / 2 + 10}`}>
      {zones.map(([from, to, zc]) => {
        const fa = Math.PI + (from / 100) * Math.PI;
        const ta = Math.PI + (to / 100) * Math.PI;
        return (
          <path
            key={from}
            d={`M ${cx + R * Math.cos(fa)} ${cy + R * Math.sin(fa)} A ${R} ${R} 0 0 1 ${cx + R * Math.cos(ta)} ${cy + R * Math.sin(ta)}`}
            fill="none" stroke={zc} strokeWidth="8" strokeOpacity="0.25"
          />
        );
      })}
      {/* Active arc */}
      <path
        d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${x} ${y}`}
        fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
        style={{ transition: "all 0.8s ease" }}
      />
      {/* Needle */}
      <line x1={cx} y1={cy} x2={cx + (R - 12) * Math.cos(angle)} y2={cy + (R - 12) * Math.sin(angle)}
        stroke={color} strokeWidth="2.5" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="5" fill={color} />
      {/* Value */}
      <text x={cx} y={cy - 5} textAnchor="middle" fontSize="22" fontWeight="700"
        fill={color} fontFamily="'JetBrains Mono', monospace">{value}</text>
    </svg>
  );
}

function SentimentCard({ sentiment, loading }) {
  if (loading) {
    return (
      <div className="card flex items-center justify-center h-48">
        <div className="w-5 h-5 border-2 border-brand-amber border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!sentiment) return null;

  const score = Math.round(50 + (sentiment.overall_score ?? 0) * 50);
  const isPos = (sentiment.overall_score ?? 0) >= 0.1;
  const isNeg = (sentiment.overall_score ?? 0) <= -0.1;
  const label = isPos ? "Bullish" : isNeg ? "Bearish" : "Neutral";
  const labelColor = isPos ? "#00c896" : isNeg ? "#ef4444" : "#f59e0b";

  const pos = sentiment.positive_pct ?? Math.max(10, Math.min(90, score));
  const neg = sentiment.negative_pct ?? Math.max(5, 100 - pos - 20);
  const neu = Math.max(0, 100 - pos - neg);

  return (
    <div className="card">
      <div className="text-sm font-semibold text-tx-muted mb-3">Sentiment</div>

      <div className="flex flex-col items-center">
        <ArcGauge value={score} size={160} />
        <div className="text-sm font-bold -mt-1" style={{ color: labelColor }}>{label}</div>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-3 gap-2 mt-4 text-center">
        <div>
          <div className="text-sm font-bold text-brand-green">{pos}%</div>
          <div className="text-xs text-tx-muted">Positive</div>
        </div>
        <div>
          <div className="text-sm font-bold text-tx-muted">{neu}%</div>
          <div className="text-xs text-tx-muted">Neutral</div>
        </div>
        <div>
          <div className="text-sm font-bold text-brand-red">{neg}%</div>
          <div className="text-xs text-tx-muted">Negative</div>
        </div>
      </div>

      {/* Sources */}
      <div className="mt-4">
        <div className="text-xs text-tx-muted mb-2">Sources</div>
        <div className="flex items-center gap-3">
          {/* Twitter */}
          <div className="w-7 h-7 rounded-full bg-[#1da1f2]/15 border border-[#1da1f2]/30 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="#1da1f2">
              <path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z" />
            </svg>
          </div>
          {/* Reddit */}
          <div className="w-7 h-7 rounded-full bg-[#ff4500]/15 border border-[#ff4500]/30 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="#ff4500">
              <circle cx="12" cy="12" r="10" />
              <path fill="white" d="M19.49 12c0-.907-.74-1.64-1.65-1.64-.44 0-.84.17-1.14.45a8.16 8.16 0 0 0-4.14-1.3l.7-3.28 2.28.48a1.16 1.16 0 1 0 .12-.56l-2.54-.54-.79 3.7a8.19 8.19 0 0 0-4.1 1.29 1.65 1.65 0 1 0-1.83 2.58 3.1 3.1 0 0 0-.04.5c0 2.57 3 4.65 6.65 4.65s6.65-2.08 6.65-4.65c0-.17-.01-.33-.04-.5a1.64 1.64 0 0 0 .03-2.68zm-9.69 1.24a.9.9 0 1 1 1.8 0 .9.9 0 0 1-1.8 0zm5.02 2.37c-.62.62-1.8.67-2.14.67-.34 0-1.52-.05-2.14-.67a.22.22 0 0 1 .31-.31c.39.39 1.22.53 1.83.53s1.44-.14 1.83-.53a.22.22 0 0 1 .31.31zm-.17-1.47a.9.9 0 1 1 0-1.8.9.9 0 0 1 0 1.8z" />
            </svg>
          </div>
          {/* News */}
          <div className="w-7 h-7 rounded-full bg-tx-muted/10 border border-border flex items-center justify-center">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="#5a5e7a" strokeWidth="2">
              <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" />
            </svg>
          </div>
          {/* F&G */}
          <div className="w-7 h-7 rounded-full bg-brand-amber/10 border border-brand-amber/30 flex items-center justify-center">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="#f59e0b" strokeWidth="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Fear & Greed Card ────────────────────────────────────────────────────────

function FearGreedCard({ sentiment, loading }) {
  if (loading) {
    return (
      <div className="card flex items-center justify-center h-48">
        <div className="w-5 h-5 border-2 border-brand-amber border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!sentiment) return null;

  const value = sentiment.fear_greed?.value ?? 50;
  const fgLabel = sentiment.fear_greed?.classification ?? "Neutral";
  const color =
    value >= 75 ? "#00c896" :
    value >= 55 ? "#86efac" :
    value >= 45 ? "#f59e0b" :
    value >= 25 ? "#f97316" :
    "#ef4444";

  const description =
    value >= 75
      ? `The market is currently in Extreme Greed. Investors may be overly confident — exercise caution.`
      : value >= 55
      ? `The market is currently ${fgLabel}. Investors are confident and willing to take on higher risks.`
      : value >= 45
      ? `The market is currently Neutral. No strong directional bias at this time.`
      : value >= 25
      ? `The market is in Fear. Investors are nervous — potential buying opportunities may arise.`
      : `The market is in Extreme Fear. This has historically been a good buying opportunity.`;

  return (
    <div className="card">
      <div className="text-sm font-semibold text-tx-muted mb-3">Fear &amp; Greed Index</div>

      <div className="flex flex-col items-center">
        <ArcGauge value={value} size={160} />
        <div className="text-sm font-bold -mt-1" style={{ color }}>{fgLabel}</div>
      </div>

      <p className="text-xs text-tx-muted mt-4 leading-relaxed">
        The market is currently{" "}
        <span style={{ color }} className="font-semibold">{fgLabel}</span>.{" "}
        {value >= 55
          ? "Investors are more confident and willing to take on higher risks."
          : value >= 45
          ? "Markets are balanced between optimism and caution."
          : "Investors are nervous — consider watching for oversold conditions."}
      </p>

      <button className="mt-3 text-xs text-brand-blue hover:text-brand-blue/80 transition-colors underline underline-offset-2">
        View historical chart
      </button>
    </div>
  );
}

// ── Combined Right Panel ─────────────────────────────────────────────────────

export default function RightPanel({ signal, signalLoading, sentiment, sentimentLoading }) {
  return (
    <div className="w-[300px] shrink-0 flex flex-col gap-3 overflow-y-auto no-scrollbar border-l border-border p-3">
      <SignalCard signal={signal} loading={signalLoading} />
      <SentimentCard sentiment={sentiment} loading={sentimentLoading} />
      <FearGreedCard sentiment={sentiment} loading={sentimentLoading} />
    </div>
  );
}
