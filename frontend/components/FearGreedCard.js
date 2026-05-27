export default function FearGreedCard({ data, loading }) {
  if (loading) {
    return (
      <div className="card flex items-center justify-center h-40">
        <div className="w-5 h-5 border-2 border-brand-amber border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!data) return null;

  const value = data.fear_greed?.value ?? 50;
  const label = data.fear_greed?.classification ?? "Neutral";

  const color =
    value >= 75 ? "#22c55e" :
    value >= 55 ? "#86efac" :
    value >= 45 ? "#f59e0b" :
    value >= 25 ? "#f97316" :
    "#ef4444";

  // Arc parameters (half-circle)
  const R = 52;
  const cx = 70, cy = 70;
  const angle = Math.PI + (value / 100) * Math.PI;
  const x = cx + R * Math.cos(angle);
  const y = cy + R * Math.sin(angle);

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-slate-500 uppercase tracking-wider">Fear &amp; Greed</span>
        <span className="text-xs text-slate-600 font-mono">alternative.me</span>
      </div>

      <div className="flex flex-col items-center">
        <svg width="140" height="82" viewBox="0 0 140 82">
          {/* Color zones */}
          {[
            { from: 0, to: 25, color: "#ef4444" },
            { from: 25, to: 45, color: "#f97316" },
            { from: 45, to: 55, color: "#f59e0b" },
            { from: 55, to: 75, color: "#86efac" },
            { from: 75, to: 100, color: "#22c55e" },
          ].map(({ from, to, color: zoneColor }) => {
            const fromAngle = Math.PI + (from / 100) * Math.PI;
            const toAngle = Math.PI + (to / 100) * Math.PI;
            const x1 = cx + R * Math.cos(fromAngle);
            const y1 = cy + R * Math.sin(fromAngle);
            const x2 = cx + R * Math.cos(toAngle);
            const y2 = cy + R * Math.sin(toAngle);
            const largeArc = (to - from) > 50 ? 1 : 0;
            return (
              <path
                key={from}
                d={`M ${x1} ${y1} A ${R} ${R} 0 ${largeArc} 1 ${x2} ${y2}`}
                fill="none"
                stroke={zoneColor}
                strokeWidth="8"
                strokeOpacity="0.3"
              />
            );
          })}

          {/* Background arc */}
          <path
            d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`}
            fill="none" stroke="#334155" strokeWidth="3"
          />

          {/* Value arc */}
          <path
            d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${x} ${y}`}
            fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
            style={{ transition: "all 0.8s ease" }}
          />

          {/* Needle */}
          <line
            x1={cx} y1={cy}
            x2={cx + (R - 14) * Math.cos(angle)}
            y2={cy + (R - 14) * Math.sin(angle)}
            stroke={color} strokeWidth="2.5" strokeLinecap="round"
          />
          <circle cx={cx} cy={cy} r="5" fill={color} />

          {/* Value text */}
          <text x={cx} y={cy - 6} textAnchor="middle" fontSize="20" fontWeight="bold"
            fill={color} fontFamily="monospace">{value}</text>
        </svg>

        <span className="text-sm font-semibold -mt-2" style={{ color }}>{label}</span>

        {/* Scale labels */}
        <div className="flex justify-between w-full px-2 mt-1 text-xs text-slate-600">
          <span>Fear</span>
          <span>Neutral</span>
          <span>Greed</span>
        </div>

        {/* Sentiment breakdown */}
        {data.positive_pct != null && (
          <div className="flex items-center justify-center gap-4 mt-3 text-xs w-full">
            <div className="text-center">
              <div className="text-brand-green font-bold">{data.positive_pct}%</div>
              <div className="text-slate-500">Positive</div>
            </div>
            <div className="text-center">
              <div className="text-slate-400 font-bold">{data.neutral_pct}%</div>
              <div className="text-slate-500">Neutral</div>
            </div>
            <div className="text-center">
              <div className="text-brand-red font-bold">{data.negative_pct}%</div>
              <div className="text-slate-500">Negative</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
