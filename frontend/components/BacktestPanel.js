import { useState } from "react";
import clsx from "clsx";

function MetricCard({ label, value, sub, color }) {
  return (
    <div className="bg-surface-2/50 rounded-lg p-3">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className={clsx("text-lg font-bold font-mono", color ?? "text-slate-200")}>{value}</div>
      {sub && <div className="text-xs text-slate-600 mt-0.5">{sub}</div>}
    </div>
  );
}

function MiniEquityCurve({ trades }) {
  if (!trades || trades.length === 0) return null;

  let equity = 100;
  const points = [equity];
  for (const t of trades) {
    equity = equity * (1 + t.pnl_pct / 100);
    points.push(equity);
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = 300, h = 80;

  const pathD = points
    .map((v, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 10) - 5;
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  const isPositive = points[points.length - 1] >= 100;
  const lineColor = isPositive ? "#22c55e" : "#ef4444";
  const fillColor = isPositive ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)";

  const fillPath = `${pathD} L ${w} ${h} L 0 ${h} Z`;

  return (
    <div className="mt-3">
      <div className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Equity Curve</div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-20 rounded-lg bg-surface-2/30">
        <path d={fillPath} fill={fillColor} />
        <path d={pathD} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinejoin="round" />
        {/* Baseline at 100 */}
        <line
          x1={0} y1={h - ((100 - min) / range) * (h - 10) - 5}
          x2={w} y2={h - ((100 - min) / range) * (h - 10) - 5}
          stroke="#475569" strokeWidth="0.5" strokeDasharray="4,4"
        />
      </svg>
    </div>
  );
}

function TradeRow({ trade, i }) {
  const isWin = trade.outcome === "WIN";
  return (
    <tr className={clsx("text-xs", isWin ? "" : "opacity-80")}>
      <td className="py-1.5 px-2 text-slate-500">#{i + 1}</td>
      <td className="py-1.5 px-2">
        <span className={trade.direction === "LONG" ? "badge-long" : "badge-short"} style={{ fontSize: "10px" }}>
          {trade.direction}
        </span>
      </td>
      <td className="py-1.5 px-2 text-slate-400">{new Date(trade.entry_time).toLocaleDateString()}</td>
      <td className={clsx("py-1.5 px-2 font-mono font-medium", isWin ? "text-brand-green" : "text-brand-red")}>
        {trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(2)}%
      </td>
      <td className="py-1.5 px-2 text-slate-500">{trade.bars_held}b</td>
      <td className="py-1.5 px-2">
        <span className={clsx("text-xs font-medium", isWin ? "text-brand-green" : "text-brand-red")}>
          {trade.outcome}
        </span>
      </td>
    </tr>
  );
}

export default function BacktestPanel({ symbol, onRunBacktest, result, loading }) {
  const [timeframe, setTimeframe] = useState("1h");
  const [limit, setLimit] = useState(500);

  const tfs = ["15m", "30m", "1h", "4h", "1d"];

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-semibold text-slate-200">Backtesting Engine</span>
        <span className="text-xs text-slate-500 bg-surface-2 px-2 py-0.5 rounded">
          EMA 7/25 Cross Strategy
        </span>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-500">Timeframe:</span>
          {tfs.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={clsx(
                "px-2 py-1 rounded text-xs transition-colors",
                timeframe === tf
                  ? "bg-brand-blue text-white"
                  : "bg-surface-2 text-slate-400 hover:text-slate-200"
              )}
            >
              {tf}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-500">Candles:</span>
          {[200, 500, 1000].map((l) => (
            <button
              key={l}
              onClick={() => setLimit(l)}
              className={clsx(
                "px-2 py-1 rounded text-xs transition-colors",
                limit === l
                  ? "bg-slate-600 text-slate-200"
                  : "bg-surface-2 text-slate-400 hover:text-slate-200"
              )}
            >
              {l}
            </button>
          ))}
        </div>

        <button
          onClick={() => onRunBacktest(symbol, timeframe, limit)}
          disabled={!symbol || loading}
          className={clsx(
            "px-4 py-1.5 rounded-lg text-xs font-semibold transition-all",
            symbol && !loading
              ? "bg-brand-blue text-white hover:bg-blue-500"
              : "bg-surface-2 text-slate-600 cursor-not-allowed"
          )}
        >
          {loading ? (
            <span className="flex items-center gap-1">
              <div className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
              Running…
            </span>
          ) : (
            `Run Backtest${symbol ? ` · ${symbol}` : ""}`
          )}
        </button>
      </div>

      {result && (
        <>
          {/* Metrics grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
            <MetricCard
              label="Win Rate"
              value={`${result.win_rate}%`}
              sub={`${result.total_trades} trades`}
              color={result.win_rate >= 55 ? "text-brand-green" : result.win_rate >= 45 ? "text-brand-amber" : "text-brand-red"}
            />
            <MetricCard
              label="Profit Factor"
              value={result.profit_factor}
              sub="gross profit/loss"
              color={result.profit_factor >= 1.5 ? "text-brand-green" : result.profit_factor >= 1 ? "text-brand-amber" : "text-brand-red"}
            />
            <MetricCard
              label="Max Drawdown"
              value={`${result.max_drawdown}%`}
              sub="peak-to-trough"
              color={result.max_drawdown <= 10 ? "text-brand-green" : result.max_drawdown <= 20 ? "text-brand-amber" : "text-brand-red"}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={result.sharpe_ratio}
              sub="risk-adjusted return"
              color={result.sharpe_ratio >= 1.5 ? "text-brand-green" : result.sharpe_ratio >= 0.8 ? "text-brand-amber" : "text-brand-red"}
            />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
            <MetricCard
              label="Total Return"
              value={`${result.total_return_pct >= 0 ? "+" : ""}${result.total_return_pct}%`}
              color={result.total_return_pct >= 0 ? "text-brand-green" : "text-brand-red"}
            />
            <MetricCard label="Best Trade" value={`+${result.best_trade_pct}%`} color="text-brand-green" />
            <MetricCard label="Worst Trade" value={`${result.worst_trade_pct}%`} color="text-brand-red" />
            <MetricCard
              label="Avg Duration"
              value={`${result.avg_trade_duration_hours}h`}
              sub={result.timeframe}
            />
          </div>

          {/* Equity curve */}
          <MiniEquityCurve trades={result.trades} />

          {/* Trade list */}
          {result.trades?.length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                Recent Trades (last {result.trades.length})
              </div>
              <div className="overflow-x-auto max-h-48 overflow-y-auto rounded-lg bg-surface-2/30">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-surface-2">
                      <th className="py-1.5 px-2 text-left text-slate-500 font-medium">#</th>
                      <th className="py-1.5 px-2 text-left text-slate-500 font-medium">Dir</th>
                      <th className="py-1.5 px-2 text-left text-slate-500 font-medium">Date</th>
                      <th className="py-1.5 px-2 text-left text-slate-500 font-medium">P&L</th>
                      <th className="py-1.5 px-2 text-left text-slate-500 font-medium">Bars</th>
                      <th className="py-1.5 px-2 text-left text-slate-500 font-medium">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t, i) => (
                      <TradeRow key={i} trade={t} i={i} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {!result && !loading && (
        <div className="text-center text-slate-600 text-xs py-8">
          Select a coin and click Run Backtest to see historical performance
        </div>
      )}
    </div>
  );
}
