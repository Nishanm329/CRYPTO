import clsx from "clsx";

function FearGreedGauge({ value, classification }) {
  // Arc gauge: 0 = extreme fear (red), 100 = extreme greed (green)
  const color =
    value >= 75 ? "#22c55e" :
    value >= 55 ? "#86efac" :
    value >= 45 ? "#f59e0b" :
    value >= 25 ? "#f97316" :
    "#ef4444";

  const label =
    value >= 75 ? "Extreme Greed" :
    value >= 55 ? "Greed" :
    value >= 45 ? "Neutral" :
    value >= 25 ? "Fear" :
    "Extreme Fear";

  // SVG arc parameters
  const R = 52;
  const cx = 70, cy = 70;
  const startAngle = Math.PI;
  const endAngle = 2 * Math.PI;
  const angle = startAngle + (value / 100) * Math.PI;
  const x = cx + R * Math.cos(angle);
  const y = cy + R * Math.sin(angle);

  return (
    <div className="flex flex-col items-center">
      <svg width="140" height="80" viewBox="0 0 140 80">
        {/* Background arc */}
        <path
          d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`}
          fill="none" stroke="#334155" strokeWidth="10" strokeLinecap="round"
        />
        {/* Colored arc */}
        <path
          d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${x} ${y}`}
          fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          style={{ transition: "all 0.8s ease" }}
        />
        {/* Needle */}
        <line
          x1={cx} y1={cy}
          x2={cx + (R - 12) * Math.cos(angle)}
          y2={cy + (R - 12) * Math.sin(angle)}
          stroke={color} strokeWidth="2" strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="4" fill={color} />
        {/* Value */}
        <text x={cx} y={cy - 8} textAnchor="middle" fontSize="22" fontWeight="bold"
          fill={color} fontFamily="monospace">{value}</text>
      </svg>
      <span className="text-sm font-semibold -mt-1" style={{ color }}>{label}</span>
    </div>
  );
}

function SentimentBar({ label, value, color }) {
  const pct = Math.round(Math.abs(value) * 100);
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500 w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono w-8 text-right" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

export default function SentimentPanel({ sentiment, loading }) {
  if (loading) {
    return (
      <div className="card flex items-center justify-center h-48">
        <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!sentiment) return null;

  const score = sentiment.overall_score ?? 0;
  const fg = sentiment.fear_greed;
  const isPositive = score >= 0.1;
  const isNegative = score <= -0.1;
  const scoreColor = isPositive ? "#22c55e" : isNegative ? "#ef4444" : "#f59e0b";

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-semibold text-slate-200">Market Sentiment</span>
        <span
          className={clsx(
            "text-xs font-bold px-2 py-0.5 rounded border",
            isPositive ? "bg-green-500/10 border-green-500/30 text-brand-green" :
            isNegative ? "bg-red-500/10 border-red-500/30 text-brand-red" :
            "bg-amber-500/10 border-amber-500/30 text-brand-amber"
          )}
        >
          {sentiment.classification}
        </span>
      </div>

      <div className="flex items-center justify-between gap-4">
        {/* Fear & Greed gauge */}
        <div className="flex flex-col items-center gap-1">
          <span className="text-xs text-slate-500 uppercase tracking-wider">Fear & Greed</span>
          <FearGreedGauge value={fg.value} classification={fg.classification} />
          <span className="text-xs text-slate-600">{fg.classification}</span>
        </div>

        {/* Composite score */}
        <div className="flex-1">
          <div className="text-center mb-3">
            <div className="text-2xl font-bold" style={{ color: scoreColor }}>
              {score >= 0 ? "+" : ""}{(score * 100).toFixed(0)}
            </div>
            <div className="text-xs text-slate-500">Composite Score</div>
          </div>

          <div className="space-y-2">
            <SentimentBar
              label="Fear/Greed"
              value={(fg.value - 50) / 50}
              color={fg.value >= 50 ? "#22c55e" : "#ef4444"}
            />
            <SentimentBar
              label="Social"
              value={0}
              color="#94a3b8"
            />
            <SentimentBar
              label="News NLP"
              value={0}
              color="#94a3b8"
            />
          </div>

          <div className="mt-3 text-xs text-slate-600 italic text-center">
            Social & News NLP available in Pro
          </div>
        </div>
      </div>
    </div>
  );
}
