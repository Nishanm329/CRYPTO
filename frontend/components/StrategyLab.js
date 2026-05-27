import { useState, useCallback } from "react";
import clsx from "clsx";
import { api } from "../lib/api";

// ── Colour helpers ────────────────────────────────────────────────────────────

const rankColor = (rank) =>
  rank === 1 ? "#f4b942" : rank === 2 ? "#9ca3af" : rank === 3 ? "#b45309" : null;

const metricColor = (val, good, bad) => {
  if (val >= good) return "text-brand-green";
  if (val >= (good + bad) / 2) return "text-brand-amber";
  return "text-brand-red";
};

const filterBadgeColor = {
  rsi: "bg-purple-500/15 text-purple-300 border-purple-500/25",
  macd: "bg-brand-blue/15 text-blue-300 border-brand-blue/25",
  bb: "bg-brand-amber/15 text-amber-300 border-brand-amber/25",
  volume: "bg-brand-green/15 text-green-300 border-brand-green/25",
  stochrsi: "bg-pink-500/15 text-pink-300 border-pink-500/25",
};

// ── Mini sparkline equity curve ───────────────────────────────────────────────

function Sparkline({ points, width = 140, height = 36 }) {
  if (!points || points.length < 2) return null;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const W = width, H = height;

  const coords = points.map((v, i) => {
    const x = (i / (points.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 4) - 2;
    return [x, y];
  });

  const linePath = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x} ${y}`).join(" ");
  const fillPath = `${linePath} L${W} ${H} L0 ${H} Z`;
  const isUp = points[points.length - 1] >= 100;
  const stroke = isUp ? "#00c896" : "#ef4444";
  const fill = isUp ? "rgba(0,200,150,0.08)" : "rgba(239,68,68,0.08)";

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      <path d={fillPath} fill={fill} />
      <path d={linePath} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

// ── Large equity curve for expanded row ──────────────────────────────────────

function EquityCurve({ points }) {
  if (!points || points.length < 2) return null;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const W = 500, H = 100;
  const pad = { top: 8, right: 8, bottom: 20, left: 40 };
  const iW = W - pad.left - pad.right;
  const iH = H - pad.top - pad.bottom;

  const coords = points.map((v, i) => {
    const x = pad.left + (i / (points.length - 1)) * iW;
    const y = pad.top + iH - ((v - min) / range) * iH;
    return [x, y];
  });

  const linePath = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x} ${y}`).join(" ");
  const fillPath = `${linePath} L${W - pad.right} ${H - pad.bottom} L${pad.left} ${H - pad.bottom} Z`;

  // Baseline y at value=100
  const baselineY = pad.top + iH - ((100 - min) / range) * iH;

  const isUp = points[points.length - 1] >= 100;
  const stroke = isUp ? "#00c896" : "#ef4444";
  const fill = isUp ? "rgba(0,200,150,0.08)" : "rgba(239,68,68,0.08)";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      {/* Y-axis labels */}
      {[min, 100, max].map((v) => {
        const y = pad.top + iH - ((v - min) / range) * iH;
        return (
          <text key={v} x={pad.left - 4} y={y + 4} fontSize="9" fill="#5a5e7a" textAnchor="end">
            {v.toFixed(0)}
          </text>
        );
      })}
      {/* Baseline */}
      <line
        x1={pad.left} y1={baselineY}
        x2={W - pad.right} y2={baselineY}
        stroke="#3a3d5c" strokeWidth="0.8" strokeDasharray="4,3"
      />
      <path d={fillPath} fill={fill} />
      <path d={linePath} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

// ── Filter badge ──────────────────────────────────────────────────────────────

function FilterBadge({ name }) {
  const cls = filterBadgeColor[name] ?? "bg-border text-tx-muted border-border";
  return (
    <span className={clsx("text-[10px] font-medium px-1.5 py-0.5 rounded border uppercase tracking-wide", cls)}>
      {name}
    </span>
  );
}

// ── Individual result row ─────────────────────────────────────────────────────

function ResultRow({ result, isExpanded, onToggle }) {
  const rc = rankColor(result.rank);
  const returnPos = result.total_return_pct >= 0;

  return (
    <>
      <tr
        onClick={onToggle}
        className={clsx(
          "border-b border-border/40 cursor-pointer transition-colors",
          isExpanded ? "bg-brand-blue/5" : "hover:bg-border/20"
        )}
      >
        {/* Rank */}
        <td className="py-2.5 pl-4 pr-2 w-8">
          <span
            className="text-sm font-bold font-mono"
            style={{ color: rc ?? "#5a5e7a" }}
          >
            #{result.rank}
          </span>
        </td>

        {/* Name + description */}
        <td className="py-2.5 pr-3">
          <div className="text-xs font-semibold text-tx">{result.name}</div>
          <div className="text-[10px] text-tx-muted mt-0.5 leading-relaxed hidden lg:block">
            {result.description}
          </div>
          {result.filters.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {result.filters.map((f) => (
                <FilterBadge key={f} name={f} />
              ))}
            </div>
          )}
        </td>

        {/* Trades */}
        <td className="py-2.5 pr-3 text-center">
          <span className="text-xs font-mono text-tx">{result.total_trades}</span>
        </td>

        {/* Win Rate */}
        <td className="py-2.5 pr-3 text-center">
          <span className={clsx("text-xs font-bold font-mono", metricColor(result.win_rate, 55, 40))}>
            {result.win_rate}%
          </span>
        </td>

        {/* Profit Factor */}
        <td className="py-2.5 pr-3 text-center">
          <span className={clsx("text-xs font-bold font-mono", metricColor(result.profit_factor, 1.5, 1.0))}>
            {result.profit_factor}×
          </span>
        </td>

        {/* Sharpe */}
        <td className="py-2.5 pr-3 text-center">
          <span className={clsx("text-xs font-bold font-mono", metricColor(result.sharpe_ratio, 0.8, 0))}>
            {result.sharpe_ratio}
          </span>
        </td>

        {/* Max DD */}
        <td className="py-2.5 pr-3 text-center">
          <span className={clsx("text-xs font-mono", result.max_drawdown <= 15 ? "text-brand-green" : result.max_drawdown <= 30 ? "text-brand-amber" : "text-brand-red")}>
            {result.max_drawdown}%
          </span>
        </td>

        {/* Total Return */}
        <td className="py-2.5 pr-3 text-center">
          <span className={clsx("text-xs font-bold font-mono", returnPos ? "text-brand-green" : "text-brand-red")}>
            {returnPos ? "+" : ""}{result.total_return_pct}%
          </span>
        </td>

        {/* Sparkline */}
        <td className="py-2 pr-4">
          <Sparkline points={result.equity_curve} />
        </td>
      </tr>

      {/* Expanded detail row */}
      {isExpanded && (
        <tr className="bg-bg-card/60">
          <td colSpan={9} className="px-6 py-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Equity curve */}
              <div className="lg:col-span-2">
                <div className="text-[10px] text-tx-muted uppercase tracking-wider mb-2">
                  Equity Curve (starting capital = 100)
                </div>
                <div className="bg-bg border border-border rounded-lg p-3">
                  <EquityCurve points={result.equity_curve} />
                </div>
              </div>

              {/* Stats grid */}
              <div>
                <div className="text-[10px] text-tx-muted uppercase tracking-wider mb-2">
                  Detailed Stats
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: "Best Trade", val: `+${result.best_trade_pct}%`, cls: "text-brand-green" },
                    { label: "Worst Trade", val: `${result.worst_trade_pct}%`, cls: "text-brand-red" },
                    { label: "Avg Duration", val: `${result.avg_bars} bars`, cls: "text-tx" },
                    { label: "Filter Count", val: `${result.filter_count} indicators`, cls: "text-tx" },
                    { label: "Profit Factor", val: `${result.profit_factor}×`, cls: metricColor(result.profit_factor, 1.5, 1.0) },
                    { label: "Max Drawdown", val: `${result.max_drawdown}%`, cls: result.max_drawdown <= 15 ? "text-brand-green" : "text-brand-red" },
                  ].map(({ label, val, cls }) => (
                    <div key={label} className="bg-bg border border-border rounded-lg p-2.5">
                      <div className="text-[10px] text-tx-muted mb-0.5">{label}</div>
                      <div className={clsx("text-sm font-bold font-mono", cls)}>{val}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Controls ──────────────────────────────────────────────────────────────────

const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"];
const TIMEFRAMES = ["1d", "4h", "1w"];
const YEARS = [1, 2, 3, 6];

// ── Main component ────────────────────────────────────────────────────────────

export default function StrategyLab({ defaultSymbol = "BTCUSDT" }) {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [timeframe, setTimeframe] = useState("1d");
  const [years, setYears] = useState(6);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const runBacktest = useCallback(async () => {
    setLoading(true);
    setError(null);
    setData(null);
    setExpandedId(null);
    try {
      const result = await api.combinationBacktest(symbol, timeframe, years);
      setData(result);
      // Auto-expand the top result
      if (result.results?.length > 0) {
        setExpandedId(result.results[0].id);
      }
    } catch (e) {
      setError(e.message ?? "Failed to run backtest");
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, years]);

  const toggleExpand = (id) => setExpandedId((prev) => (prev === id ? null : id));

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg">
      {/* ── Page header ─────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-border px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-base font-bold text-tx">Strategy Lab</h1>
            <p className="text-xs text-tx-muted mt-0.5">
              Backtest 12 indicator combinations on up to 6 years of real Binance data.
              Ranked by risk-adjusted Sharpe ratio.
            </p>
          </div>

          {data && (
            <div className="shrink-0 text-right">
              <div className="text-[10px] text-tx-muted">Best strategy</div>
              <div className="text-sm font-bold text-brand-gold">{data.best_combination}</div>
              <div className="text-[10px] text-tx-muted mt-0.5">
                {data.start_date?.slice(0, 10)} → {data.end_date?.slice(0, 10)}
                {" · "}{data.total_bars} bars
              </div>
            </div>
          )}
        </div>

        {/* ── Controls ──────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-3 mt-4">
          {/* Symbol */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-tx-muted">Pair</span>
            <div className="flex gap-0.5 bg-bg-card border border-border rounded-lg p-0.5">
              {SYMBOLS.map((s) => (
                <button
                  key={s}
                  onClick={() => setSymbol(s)}
                  className={clsx(
                    "px-2.5 py-1 text-xs font-semibold rounded-md transition-all",
                    symbol === s ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
                  )}
                >
                  {s.replace("USDT", "")}
                </button>
              ))}
            </div>
          </div>

          {/* Timeframe */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-tx-muted">TF</span>
            <div className="flex gap-0.5 bg-bg-card border border-border rounded-lg p-0.5">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={clsx(
                    "px-2.5 py-1 text-xs font-semibold rounded-md transition-all",
                    timeframe === tf ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
                  )}
                >
                  {tf.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Years */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-tx-muted">History</span>
            <div className="flex gap-0.5 bg-bg-card border border-border rounded-lg p-0.5">
              {YEARS.map((y) => (
                <button
                  key={y}
                  onClick={() => setYears(y)}
                  className={clsx(
                    "px-2.5 py-1 text-xs font-semibold rounded-md transition-all",
                    years === y ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
                  )}
                >
                  {y}Y
                </button>
              ))}
            </div>
          </div>

          {/* Run button */}
          <button
            onClick={runBacktest}
            disabled={loading}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all",
              loading
                ? "bg-brand-blue/30 text-brand-blue cursor-not-allowed"
                : "bg-brand-blue hover:bg-blue-500 text-white"
            )}
          >
            {loading ? (
              <>
                <div className="w-3 h-3 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
                <span>Fetching {years}y of {symbol.replace("USDT", "/USDT")} data…</span>
              </>
            ) : (
              <>
                <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" stroke="none" />
                </svg>
                Run Strategy Lab
              </>
            )}
          </button>

          {loading && (
            <span className="text-[10px] text-tx-muted animate-pulse">
              Paginating Binance API · computing 12 combinations…
            </span>
          )}
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {/* Error */}
        {error && (
          <div className="m-6 p-4 bg-brand-red/10 border border-brand-red/30 rounded-xl text-xs text-brand-red">
            {error}
          </div>
        )}

        {/* Empty state */}
        {!data && !loading && !error && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-8">
            <div className="w-16 h-16 rounded-2xl bg-brand-blue/10 border border-brand-blue/20 flex items-center justify-center">
              <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="#3d7fff" strokeWidth="1.5">
                <line x1="18" y1="20" x2="18" y2="10" />
                <line x1="12" y1="20" x2="12" y2="4" />
                <line x1="6" y1="20" x2="6" y2="14" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold text-tx mb-1">No results yet</div>
              <div className="text-xs text-tx-muted max-w-sm leading-relaxed">
                Select a pair, timeframe and history window, then click{" "}
                <span className="text-brand-blue font-medium">Run Strategy Lab</span> to discover
                which indicator combination has performed best over real historical data.
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 mt-4 max-w-lg w-full">
              {["EMA Only", "EMA + RSI + MACD", "Full Confluence"].map((label) => (
                <div key={label} className="bg-bg-card border border-border rounded-xl p-3 text-xs text-tx-muted">
                  {label}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results table */}
        {data && (
          <div className="p-4">
            {/* Summary strip */}
            <div className="grid grid-cols-4 gap-3 mb-4">
              {[
                { label: "Combinations Tested", val: data.combinations_tested, cls: "text-tx" },
                { label: "Best Sharpe", val: data.best_sharpe, cls: metricColor(data.best_sharpe, 0.8, 0) },
                { label: "Bars Analysed", val: data.total_bars.toLocaleString(), cls: "text-tx" },
                { label: "Data Period", val: `${data.years_tested}Y · ${data.timeframe.toUpperCase()}`, cls: "text-tx" },
              ].map(({ label, val, cls }) => (
                <div key={label} className="bg-bg-card border border-border rounded-xl p-3">
                  <div className="text-[10px] text-tx-muted mb-1">{label}</div>
                  <div className={clsx("text-sm font-bold font-mono", cls)}>{val}</div>
                </div>
              ))}
            </div>

            {/* Leaderboard table */}
            <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-tx-muted">
                    <th className="py-2 pl-4 pr-2 text-left font-medium">#</th>
                    <th className="py-2 pr-3 text-left font-medium">Strategy</th>
                    <th className="py-2 pr-3 text-center font-medium">Trades</th>
                    <th className="py-2 pr-3 text-center font-medium">Win%</th>
                    <th className="py-2 pr-3 text-center font-medium">PF</th>
                    <th className="py-2 pr-3 text-center font-medium">Sharpe</th>
                    <th className="py-2 pr-3 text-center font-medium">Max DD</th>
                    <th className="py-2 pr-3 text-center font-medium">Return</th>
                    <th className="py-2 pr-4 text-left font-medium">Equity</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((result) => (
                    <ResultRow
                      key={result.id}
                      result={result}
                      isExpanded={expandedId === result.id}
                      onToggle={() => toggleExpand(result.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-3 text-[10px] text-tx-muted text-center leading-relaxed">
              Click any row to expand equity curve · Past performance does not guarantee future results ·
              EMA 7/25 cross base signal with ATR 2×SL / 3×TP · Overlap prevention active
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
