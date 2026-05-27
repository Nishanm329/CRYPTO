import clsx from "clsx";

// Generate a smooth sparkline SVG path from an array of values
function Sparkline({ values, positive, width = 80, height = 32 }) {
  if (!values || values.length < 2) {
    // Generate a fake plausible sparkline based on direction
    const base = positive ? 50 : 50;
    values = Array.from({ length: 20 }, (_, i) => {
      const trend = positive ? i * 0.8 : -i * 0.8;
      return base + trend + (Math.sin(i * 0.9) * 5) + (Math.cos(i * 1.3) * 3);
    });
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const pts = values.map((v, i) => ({
    x: (i / (values.length - 1)) * width,
    y: height - ((v - min) / range) * (height - 4) - 2,
  }));

  // Smooth path using bezier curves
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < pts.length; i++) {
    const cp1x = (pts[i - 1].x + pts[i].x) / 2;
    d += ` C ${cp1x} ${pts[i - 1].y}, ${cp1x} ${pts[i].y}, ${pts[i].x} ${pts[i].y}`;
  }

  const color = positive ? "#00c896" : "#ef4444";
  const fillD = `${d} L ${width} ${height} L 0 ${height} Z`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={`sg-${positive ? "up" : "dn"}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fillD} fill={`url(#sg-${positive ? "up" : "dn"})`} />
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function StatCard({ label, value, change, sparkValues, prefix = "" }) {
  const isPos = (change ?? 0) >= 0;
  return (
    <div className="flex-1 min-w-0 bg-bg-card border border-border rounded-xl px-4 py-3 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="text-xs text-tx-muted mb-1 font-medium">{label}</div>
        <div className={clsx("text-lg font-bold font-mono leading-none", isPos ? "text-brand-green" : "text-brand-red")}>
          {prefix}{value ?? "—"}
        </div>
        {change != null && (
          <div className={clsx("text-xs mt-1 font-medium", isPos ? "text-brand-green" : "text-brand-red")}>
            {isPos ? "+" : ""}{change?.toFixed(2)}%
          </div>
        )}
      </div>
      <div className="shrink-0 opacity-80">
        <Sparkline positive={isPos} values={sparkValues} />
      </div>
    </div>
  );
}

// Gauge for Fear & Greed / Market Sentiment (mini arc)
function MiniGauge({ value = 50, label }) {
  const color =
    value >= 75 ? "#00c896" :
    value >= 55 ? "#86efac" :
    value >= 45 ? "#f59e0b" :
    value >= 25 ? "#f97316" :
    "#ef4444";

  const R = 22, cx = 28, cy = 28;
  const angle = Math.PI + (value / 100) * Math.PI;
  const x = cx + R * Math.cos(angle);
  const y = cy + R * Math.sin(angle);

  return (
    <div className="flex-1 min-w-0 bg-bg-card border border-border rounded-xl px-4 py-3 flex items-center gap-3">
      <div className="min-w-0 flex-1">
        <div className="text-xs text-tx-muted mb-1 font-medium">{label}</div>
        <div className="text-lg font-bold font-mono leading-none" style={{ color }}>
          {value}
        </div>
        <div className="text-xs mt-1 font-medium" style={{ color }}>
          {value >= 75 ? "Extreme Greed" : value >= 55 ? "Greed" : value >= 45 ? "Neutral" : value >= 25 ? "Fear" : "Extreme Fear"}
        </div>
      </div>
      <div className="shrink-0">
        <svg width="56" height="32" viewBox="0 0 56 32">
          {/* Colored zones */}
          {[
            [0, 25, "#ef4444"], [25, 45, "#f97316"], [45, 55, "#f59e0b"],
            [55, 75, "#86efac"], [75, 100, "#00c896"],
          ].map(([from, to, zc]) => {
            const fa = Math.PI + (from / 100) * Math.PI;
            const ta = Math.PI + (to / 100) * Math.PI;
            return (
              <path
                key={from}
                d={`M ${cx + R * Math.cos(fa)} ${cy + R * Math.sin(fa)} A ${R} ${R} 0 0 1 ${cx + R * Math.cos(ta)} ${cy + R * Math.sin(ta)}`}
                fill="none" stroke={zc} strokeWidth="5" strokeOpacity="0.35"
              />
            );
          })}
          {/* Active arc */}
          <path
            d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${x} ${y}`}
            fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
          />
          {/* Needle */}
          <line x1={cx} y1={cy} x2={cx + (R - 7) * Math.cos(angle)} y2={cy + (R - 7) * Math.sin(angle)}
            stroke={color} strokeWidth="2" strokeLinecap="round" />
          <circle cx={cx} cy={cy} r="3" fill={color} />
        </svg>
      </div>
    </div>
  );
}

export default function StatsStrip({ marketOverview, sentiment }) {
  const btc = marketOverview?.btc;
  const eth = marketOverview?.eth;
  const fgValue = sentiment?.fear_greed?.value ?? 50;

  const btcPrice = btc?.price
    ? btc.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "—";
  const ethPrice = eth?.price
    ? eth.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "—";

  return (
    <div className="flex gap-2 px-3 py-2 shrink-0 overflow-x-auto no-scrollbar">
      {/* BTC/ETH Price Card */}
      <div className="flex-1 min-w-max bg-bg-card border border-border rounded-xl px-4 py-3 flex items-center justify-between gap-4">
        <div className="flex gap-4">
          <div className="min-w-0">
            <div className="text-xs text-tx-muted mb-1">BTC/USDT</div>
            <div className={clsx("text-lg font-bold font-mono", (btc?.change_24h ?? 0) >= 0 ? "text-brand-green" : "text-brand-red")}>
              {btcPrice}
            </div>
            {btc?.change_24h != null && (
              <div className={clsx("text-xs mt-1 font-medium", (btc?.change_24h ?? 0) >= 0 ? "text-brand-green" : "text-brand-red")}>
                {btc.change_24h >= 0 ? "+" : ""}{btc.change_24h.toFixed(2)}%
              </div>
            )}
          </div>
          <div className="w-px bg-border/30" />
          <div className="min-w-0">
            <div className="text-xs text-tx-muted mb-1">ETH/USDT</div>
            <div className={clsx("text-lg font-bold font-mono", (eth?.change_24h ?? 0) >= 0 ? "text-brand-green" : "text-brand-red")}>
              {ethPrice}
            </div>
            {eth?.change_24h != null && (
              <div className={clsx("text-xs mt-1 font-medium", (eth?.change_24h ?? 0) >= 0 ? "text-brand-green" : "text-brand-red")}>
                {eth.change_24h >= 0 ? "+" : ""}{eth.change_24h.toFixed(2)}%
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Market Health Card */}
      <div className="flex-1 min-w-max bg-bg-card border border-border rounded-xl px-4 py-3 flex items-center gap-4">
        <div className="flex-1">
          <div className="text-xs text-tx-muted mb-2">Market Health</div>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-tx-muted">BTC Dominance</span>
              <span className="font-bold text-tx">{marketOverview?.btc_dominance?.toFixed(1) ?? "—"}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-tx-muted">Market Cap</span>
              <span className="font-bold text-tx">${marketOverview?.total_mcap_trillions?.toFixed(2) ?? "—"}T</span>
            </div>
            <div className="flex justify-between">
              <span className="text-tx-muted">24h Volume</span>
              <span className="font-bold text-tx">${((btc?.volume_24h ?? 0) + (eth?.volume_24h ?? 0)) / 1e9 > 1000 ? (((btc?.volume_24h ?? 0) + (eth?.volume_24h ?? 0)) / 1e12).toFixed(1) + "T" : (((btc?.volume_24h ?? 0) + (eth?.volume_24h ?? 0)) / 1e9).toFixed(1) + "B"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sentiment Gauge */}
      <MiniGauge
        value={fgValue}
        label="Fear & Greed"
      />
    </div>
  );
}
