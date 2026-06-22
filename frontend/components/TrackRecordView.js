import useSWR from "swr";
import clsx from "clsx";
import { api } from "../lib/api";

function Stat({ label, value, sub, tone = "default" }) {
  const toneClass =
    tone === "pos" ? "text-emerald-400" :
    tone === "neg" ? "text-red-400" :
    tone === "gold" ? "text-brand-gold" : "text-tx";
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="text-[11px] uppercase tracking-wide text-tx-muted">{label}</div>
      <div className={clsx("text-2xl font-bold mt-1", toneClass)}>{value}</div>
      {sub != null && <div className="text-[11px] text-tx-muted mt-0.5">{sub}</div>}
    </div>
  );
}

function EquityCurve({ points }) {
  if (!points || points.length < 2) {
    return <div className="text-xs text-tx-muted">Not enough closed trades to plot an equity curve yet.</div>;
  }
  const w = 640, h = 160, pad = 8;
  const min = Math.min(0, ...points);
  const max = Math.max(0, ...points);
  const range = max - min || 1;
  const x = (i) => pad + (i / (points.length - 1)) * (w - pad * 2);
  const y = (v) => h - pad - ((v - min) / range) * (h - pad * 2);
  const d = points.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  const zeroY = y(0);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-40" preserveAspectRatio="none">
      <line x1={pad} y1={zeroY} x2={w - pad} y2={zeroY} stroke="#3a3f4b" strokeWidth="1" strokeDasharray="4 4" />
      <path d={d} fill="none" stroke={last >= 0 ? "#22c55e" : "#ef4444"} strokeWidth="2" />
    </svg>
  );
}

const dirClass = (d) => (d === "LONG" ? "text-emerald-400" : "text-red-400");
const rClass = (r) => (r > 0 ? "text-emerald-400" : r < 0 ? "text-red-400" : "text-tx-muted");

export default function TrackRecordView() {
  const { data, error, isLoading } = useSWR("track-record", () => api.trackRecord(), {
    refreshInterval: 60000,
    revalidateOnFocus: false,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-tx-muted">
        <div className="text-center">
          <div className="animate-spin w-6 h-6 border-2 border-brand-blue border-t-transparent rounded-full mx-auto" />
          <div className="mt-3 text-sm">Building verified track record…</div>
          <div className="text-xs text-tx-muted mt-1">Forward-testing published signals on real price data</div>
        </div>
      </div>
    );
  }
  if (error) {
    return <div className="p-6 text-red-400 text-sm">Failed to load track record: {String(error.message || error)}</div>;
  }

  const s = data || {};
  const wr = s.win_rate ?? 0;

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <h1 className="text-lg font-bold text-tx">Verified Track Record</h1>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-brand-blue/15 text-brand-blue font-semibold">
            forward-tested
          </span>
        </div>
        <p className="text-xs text-tx-muted mt-1">
          Every published signal (confidence ≥ 60) is logged at emit time and forward-tested against real
          candles to a resolved win/loss. No cherry-picking — these are the actual outcomes.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Win Rate" value={`${wr}%`} sub={`${s.wins ?? 0}W / ${s.losses ?? 0}L`} tone={wr >= 50 ? "pos" : "neg"} />
        <Stat label="Avg R / trade" value={`${(s.avg_r ?? 0) >= 0 ? "+" : ""}${s.avg_r ?? 0}R`} tone={(s.avg_r ?? 0) >= 0 ? "pos" : "neg"} />
        <Stat label="Profit Factor" value={s.profit_factor ?? 0} tone={(s.profit_factor ?? 0) >= 1 ? "pos" : "neg"} />
        <Stat label="Total R" value={`${(s.total_r ?? 0) >= 0 ? "+" : ""}${s.total_r ?? 0}R`} tone={(s.total_r ?? 0) >= 0 ? "gold" : "neg"} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Closed Trades" value={s.closed ?? 0} />
        <Stat label="Open / Tracking" value={s.open ?? 0} />
        <Stat label="Max Drawdown" value={`-${s.max_drawdown_r ?? 0}R`} tone="neg" />
        <Stat label="Best / Worst" value={`+${s.best_r ?? 0} / ${s.worst_r ?? 0}R`} />
      </div>

      <div className="bg-bg-card border border-border rounded-xl p-4">
        <div className="text-xs font-semibold text-tx mb-2">Equity Curve (cumulative R)</div>
        <EquityCurve points={s.equity_curve} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-bg-card border border-border rounded-xl p-4">
          <div className="text-xs font-semibold text-tx mb-2">By Timeframe</div>
          <div className="space-y-1.5">
            {(s.by_timeframe || []).map((b) => (
              <div key={b.key} className="flex items-center justify-between text-xs">
                <span className="text-tx font-medium">{b.key}</span>
                <span className="text-tx-muted">{b.trades} trades</span>
                <span className={clsx("font-semibold", b.win_rate >= 50 ? "text-emerald-400" : "text-red-400")}>{b.win_rate}%</span>
                <span className={clsx("font-semibold w-16 text-right", rClass(b.total_r))}>{b.total_r >= 0 ? "+" : ""}{b.total_r}R</span>
              </div>
            ))}
            {(!s.by_timeframe || s.by_timeframe.length === 0) && <div className="text-xs text-tx-muted">No closed trades yet.</div>}
          </div>
        </div>
        <div className="bg-bg-card border border-border rounded-xl p-4">
          <div className="text-xs font-semibold text-tx mb-2">By Direction</div>
          <div className="space-y-1.5">
            {(s.by_direction || []).map((b) => (
              <div key={b.key} className="flex items-center justify-between text-xs">
                <span className={clsx("font-medium", dirClass(b.key))}>{b.key}</span>
                <span className="text-tx-muted">{b.trades} trades</span>
                <span className={clsx("font-semibold", b.win_rate >= 50 ? "text-emerald-400" : "text-red-400")}>{b.win_rate}%</span>
                <span className={clsx("font-semibold w-16 text-right", rClass(b.total_r))}>{b.total_r >= 0 ? "+" : ""}{b.total_r}R</span>
              </div>
            ))}
            {(!s.by_direction || s.by_direction.length === 0) && <div className="text-xs text-tx-muted">No closed trades yet.</div>}
          </div>
        </div>
      </div>

      <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 text-xs font-semibold text-tx border-b border-border">Recent Resolved Trades</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-tx-muted text-left">
                <th className="px-4 py-2 font-medium">Pair</th>
                <th className="px-2 py-2 font-medium">TF</th>
                <th className="px-2 py-2 font-medium">Side</th>
                <th className="px-2 py-2 font-medium">Conf</th>
                <th className="px-2 py-2 font-medium">Exit</th>
                <th className="px-2 py-2 font-medium text-right">Result</th>
                <th className="px-4 py-2 font-medium text-right">Closed</th>
              </tr>
            </thead>
            <tbody>
              {(s.recent_trades || []).map((t, i) => (
                <tr key={i} className="border-t border-border/50">
                  <td className="px-4 py-2 text-tx font-medium">{t.symbol.replace("USDT", "")}</td>
                  <td className="px-2 py-2 text-tx-muted">{t.timeframe}</td>
                  <td className={clsx("px-2 py-2 font-semibold", dirClass(t.direction))}>{t.direction}</td>
                  <td className="px-2 py-2 text-tx-muted">{t.confidence}%</td>
                  <td className="px-2 py-2 text-tx-muted">{t.exit_reason}</td>
                  <td className={clsx("px-2 py-2 text-right font-bold", rClass(t.result_r ?? 0))}>
                    {t.result_r != null ? `${t.result_r >= 0 ? "+" : ""}${t.result_r}R` : "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-tx-muted">
                    {t.closed_at ? new Date(t.closed_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
              {(!s.recent_trades || s.recent_trades.length === 0) && (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-tx-muted">No resolved trades yet — check back as signals play out.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
