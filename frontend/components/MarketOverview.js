import clsx from "clsx";
import { formatChange } from "../lib/api";

function StatCell({ label, value, change, sub }) {
  const isPos = (change ?? 0) >= 0;
  return (
    <div className="flex flex-col">
      <span className="text-xs text-slate-500 mb-0.5">{label}</span>
      <span className="text-sm font-bold font-mono text-slate-100">{value}</span>
      {change != null && (
        <span className={clsx("text-xs font-mono", isPos ? "text-brand-green" : "text-brand-red")}>
          {isPos ? "+" : ""}{change?.toFixed(2)}%
        </span>
      )}
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  );
}

export default function MarketOverview({ data, loading }) {
  if (loading) {
    return (
      <div className="card">
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Market Overview</div>
        <div className="grid grid-cols-4 gap-4 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-12 bg-surface-2/50 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-500 uppercase tracking-wider">Market Overview</span>
        <span className="text-xs text-slate-600 font-mono">Binance · Live</span>
      </div>
      <div className="grid grid-cols-4 gap-4">
        <StatCell
          label="BTC/USDT"
          value={`$${data.btc?.price?.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          change={data.btc?.change_24h}
        />
        <StatCell
          label="ETH/USDT"
          value={`$${data.eth?.price?.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          change={data.eth?.change_24h}
        />
        <StatCell
          label="BTC.D"
          value={`${data.btc_dominance?.toFixed(2)}%`}
          change={data.btc_dominance_change}
        />
        <StatCell
          label="TOTAL"
          value={`$${data.total_mcap_trillions?.toFixed(2)}T`}
          change={data.total_mcap_change}
        />
      </div>
    </div>
  );
}
