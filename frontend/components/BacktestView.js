import { useState, useCallback } from "react";
import useSWR from "swr";
import { api, formatChange, formatPrice } from "../lib/api";
import clsx from "clsx";

const POPULAR = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"];

export default function BacktestView() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [years, setYears] = useState(10);
  const [triggerBacktest, setTriggerBacktest] = useState(false);

  const shouldFetch = triggerBacktest && symbol && years;

  const { data: btResult, isLoading, error, mutate } = useSWR(
    shouldFetch ? `backtest-${symbol}-${years}y` : null,
    () => api.combinationBacktest(symbol, "1d", years),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  const handleRunBacktest = useCallback(() => {
    setTriggerBacktest(true);
    mutate();
  }, [mutate]);

  const best = btResult?.results?.[0];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 border-b border-border px-5 py-3">
        <h1 className="text-sm font-bold text-tx">Backtest Lab</h1>
        <p className="text-xs text-tx-muted mt-0.5">Test 12 indicator combinations on historical data</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-5 flex flex-col gap-5">
        {/* Config */}
        <div className="bg-bg-card border border-border rounded-xl p-4 max-w-2xl">
          <div className="text-xs font-semibold text-tx mb-3">Configuration</div>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">Symbol</label>
              <select
                value={symbol}
                onChange={e => setSymbol(e.target.value)}
                disabled={isLoading}
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx outline-none focus:border-brand-blue transition-colors disabled:opacity-50"
              >
                {POPULAR.map(s => <option key={s} value={s}>{s.replace("USDT", "")}/USDT</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">Years of History</label>
              <select
                value={years}
                onChange={e => setYears(parseInt(e.target.value))}
                disabled={isLoading}
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx outline-none focus:border-brand-blue transition-colors disabled:opacity-50"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(y => <option key={y} value={y}>{y} year{y > 1 ? "s" : ""}</option>)}
              </select>
            </div>
          </div>
          <button
            onClick={handleRunBacktest}
            disabled={isLoading}
            className={clsx(
              "w-full py-2 rounded-lg text-xs font-bold transition-all",
              isLoading
                ? "bg-bg text-tx-muted cursor-not-allowed border border-border"
                : "bg-brand-blue text-white hover:bg-blue-500"
            )}
          >
            {isLoading ? "Running backtest..." : "▶ Run Backtest"}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-brand-red/10 border border-brand-red/20 rounded-xl p-4 text-xs text-brand-red max-w-2xl">
            {error.message}
          </div>
        )}

        {/* Results */}
        {btResult && (
          <>
            {/* Summary */}
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 max-w-4xl">
              <div className="bg-bg-card border border-border rounded-xl p-4">
                <div className="text-[10px] text-tx-muted mb-1">Period</div>
                <div className="text-sm font-bold text-tx">{btResult.years_tested}y backtest</div>
                <div className="text-[10px] text-tx-muted mt-1">{btResult.start_date?.split("T")[0]} → {btResult.end_date?.split("T")[0]}</div>
              </div>

              <div className="bg-bg-card border border-border rounded-xl p-4">
                <div className="text-[10px] text-tx-muted mb-1">Data Points</div>
                <div className="text-sm font-bold text-tx">{btResult.total_bars} bars</div>
                <div className="text-[10px] text-tx-muted mt-1">{btResult.combinations_tested} combinations tested</div>
              </div>

              {best && (
                <div className="bg-bg-card border border-brand-green/30 border-2 rounded-xl p-4">
                  <div className="text-[10px] text-brand-green font-bold uppercase mb-1">Best Strategy</div>
                  <div className="text-sm font-bold text-tx">{best.name}</div>
                  <div className="text-[10px] text-brand-green mt-1">Sharpe: {best.sharpe_ratio}</div>
                </div>
              )}
            </div>

            {/* Best Combination Metrics */}
            {best && (
              <div className="bg-bg-card border border-brand-green/20 rounded-xl p-4 max-w-4xl">
                <div className="text-xs font-semibold text-tx mb-3">Best Combination: {best.name}</div>
                <p className="text-[10px] text-tx-muted mb-4">{best.description}</p>

                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-3">
                  <div>
                    <div className="text-[10px] text-tx-muted mb-1">Win Rate</div>
                    <div className="text-sm font-bold text-tx">{best.win_rate}%</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-tx-muted mb-1">Profit Factor</div>
                    <div className="text-sm font-bold text-tx">{best.profit_factor}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-tx-muted mb-1">Sharpe Ratio</div>
                    <div className="text-sm font-bold text-brand-green">{best.sharpe_ratio}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-tx-muted mb-1">Max Drawdown</div>
                    <div className={clsx("text-sm font-bold", best.max_drawdown > 30 ? "text-brand-red" : "text-tx")}>
                      -{best.max_drawdown}%
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-tx-muted mb-1">Total Return</div>
                    <div className={clsx("text-sm font-bold", best.total_return_pct >= 0 ? "text-brand-green" : "text-brand-red")}>
                      {best.total_return_pct >= 0 ? "+" : ""}{best.total_return_pct}%
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-tx-muted mb-1">Total Trades</div>
                    <div className="text-sm font-bold text-tx">{best.total_trades}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-tx-muted mb-1">Avg Bars</div>
                    <div className="text-sm font-bold text-tx">{best.avg_bars}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-tx-muted mb-1">Best Trade</div>
                    <div className="text-sm font-bold text-brand-green">+{best.best_trade_pct}%</div>
                  </div>
                </div>

                {/* Equity Curve */}
                {best.equity_curve && best.equity_curve.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-border">
                    <div className="text-[10px] text-tx-muted mb-2">Equity Curve</div>
                    <EquityCurveChart data={best.equity_curve} />
                  </div>
                )}
              </div>
            )}

            {/* Leaderboard */}
            <div className="max-w-6xl">
              <div className="text-xs font-semibold text-tx mb-2">All Combinations Ranked</div>
              <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-tx-muted bg-bg/50">
                      <th className="py-2.5 pl-4 pr-2 text-left font-medium">Rank</th>
                      <th className="py-2.5 px-2 text-left font-medium">Strategy</th>
                      <th className="py-2.5 px-2 text-center font-medium">Filters</th>
                      <th className="py-2.5 px-2 text-right font-medium">Sharpe</th>
                      <th className="py-2.5 px-2 text-right font-medium">Win %</th>
                      <th className="py-2.5 px-2 text-right font-medium">P.F.</th>
                      <th className="py-2.5 px-2 text-right font-medium">Return</th>
                      <th className="py-2.5 px-2 text-right font-medium">M.D.</th>
                      <th className="py-2.5 pr-4 px-2 text-right font-medium">Trades</th>
                    </tr>
                  </thead>
                  <tbody>
                    {btResult.results?.map((r, idx) => (
                      <tr key={r.id} className={clsx(
                        "border-b border-border/40 hover:bg-border/10 transition-colors",
                        r.id === best?.id && "bg-brand-green/5"
                      )}>
                        <td className="py-3 pl-4 pr-2 font-bold text-tx">{r.rank}</td>
                        <td className="py-3 px-2">
                          <div className="font-medium text-tx">{r.name}</div>
                          <div className="text-[9px] text-tx-muted">{r.description}</div>
                        </td>
                        <td className="py-3 px-2 text-center text-tx-muted">{r.filter_count}</td>
                        <td className={clsx("py-3 px-2 text-right font-bold font-mono", r.sharpe_ratio >= 0.5 ? "text-brand-green" : "text-tx")}>
                          {r.sharpe_ratio}
                        </td>
                        <td className="py-3 px-2 text-right text-tx">{r.win_rate}%</td>
                        <td className="py-3 px-2 text-right text-tx">{r.profit_factor}</td>
                        <td className={clsx("py-3 px-2 text-right font-mono", r.total_return_pct >= 0 ? "text-brand-green" : "text-brand-red")}>
                          {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct}%
                        </td>
                        <td className={clsx("py-3 px-2 text-right text-tx", r.max_drawdown > 30 ? "text-brand-red" : "")}>
                          -{r.max_drawdown}%
                        </td>
                        <td className="py-3 pr-4 px-2 text-right text-tx">{r.total_trades}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* Empty - Show Combinations Info */}
        {!btResult && !isLoading && (
          <>
            <div className="flex flex-col items-center justify-center py-12 text-tx-muted max-w-2xl">
              <svg width="64" height="64" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="mb-4 opacity-50">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <div className="text-sm font-medium text-tx mb-1">Ready to backtest</div>
              <div className="text-xs text-tx-muted text-center">Select a symbol and year range, then run the backtest to analyze 12 indicator combinations</div>
            </div>

            {/* Show Combinations Info */}
            <div className="max-w-6xl">
              <div className="text-xs font-semibold text-tx mb-3">12 Indicator Combinations</div>
              <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-tx-muted bg-bg/50">
                      <th className="py-2.5 pl-4 pr-2 text-left font-medium">Rank</th>
                      <th className="py-2.5 px-2 text-left font-medium">Strategy Name</th>
                      <th className="py-2.5 px-2 text-left font-medium">Indicator Filters</th>
                      <th className="py-2.5 pr-4 px-2 text-left font-medium">Accuracy Profile</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { rank: 1, name: "Full Confluence", filters: "EMA + RSI + MACD + BB + Volume + StochRSI", accuracy: "Highest (6 filters)" },
                      { rank: 2, name: "EMA + RSI + MACD + BB", filters: "RSI + MACD + BB", accuracy: "Very High (4 filters)" },
                      { rank: 3, name: "EMA + RSI + MACD + Volume", filters: "RSI + MACD + Volume", accuracy: "Very High (4 filters)" },
                      { rank: 4, name: "EMA + MACD + BB", filters: "MACD + BB", accuracy: "High (3 filters)" },
                      { rank: 5, name: "EMA + RSI + Volume", filters: "RSI + Volume", accuracy: "High (3 filters)" },
                      { rank: 6, name: "EMA + RSI + MACD", filters: "RSI + MACD", accuracy: "High (3 filters)" },
                      { rank: 7, name: "EMA + Volume", filters: "Volume", accuracy: "Moderate-High (2 filters)" },
                      { rank: 8, name: "EMA + StochRSI", filters: "StochRSI", accuracy: "Moderate-High (2 filters)" },
                      { rank: 9, name: "EMA + Bollinger Bands", filters: "BB", accuracy: "Moderate (2 filters)" },
                      { rank: 10, name: "EMA + MACD", filters: "MACD", accuracy: "Moderate (2 filters)" },
                      { rank: 11, name: "EMA + RSI", filters: "RSI", accuracy: "Moderate (2 filters)" },
                      { rank: 12, name: "EMA Cross Only", filters: "Base signal (no filters)", accuracy: "Lowest (1 filter)" },
                    ].map((combo) => (
                      <tr key={combo.rank} className="border-b border-border/40 hover:bg-border/10 transition-colors">
                        <td className="py-3 pl-4 pr-2 font-bold text-brand-blue">{combo.rank}</td>
                        <td className="py-3 px-2 font-medium text-tx">{combo.name}</td>
                        <td className="py-3 px-2 text-tx-muted">{combo.filters}</td>
                        <td className="py-3 pr-4 px-2">
                          <span className={combo.rank <= 3 ? "text-brand-green font-semibold" : combo.rank <= 6 ? "text-brand-gold" : "text-tx-muted"}>
                            {combo.accuracy}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-4 text-[10px] text-tx-muted max-w-4xl">
                <p><strong>How it works:</strong> Run a backtest to test each combination on historical data. Results are ranked by Sharpe Ratio (risk-adjusted returns), not just win rate. More filters = fewer false signals but potentially fewer trades overall.</p>
              </div>

              {/* Recommendation Panel */}
              <div className="mt-6 bg-brand-blue/10 border border-brand-blue/20 rounded-xl p-4 max-w-4xl">
                <div className="text-xs font-semibold text-brand-blue mb-3">💡 Indicator Recommendation</div>
                <div className="space-y-2 text-[10px]">
                  <p><strong>Best Performing Combination:</strong> Full Confluence (6 indicators)</p>
                  <p className="text-tx-muted">To improve signal quality in the Scanner, enable these indicators in Settings:</p>
                  <div className="bg-bg-card rounded p-2 mt-2 font-mono text-[9px] space-y-1">
                    <div>✓ Bollinger Bands (BB)</div>
                    <div>✓ VWAP</div>
                    <div>✓ RSI</div>
                    <div>✓ MACD</div>
                    <div>✓ Stochastic RSI</div>
                    <div>✓ Volume Filter</div>
                  </div>
                  <button className="mt-3 text-xs px-3 py-1.5 bg-brand-blue text-white rounded hover:bg-blue-600 transition-colors">
                    ⚙️ Apply to Scanner Settings
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function EquityCurveChart({ data }) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = range * 0.1;
  const minVal = min - padding;
  const maxVal = max + padding;
  const chartHeight = 100;
  const chartWidth = Math.min(600, data.length * 2);

  const points = data.map((val, idx) => {
    const x = (idx / (data.length - 1)) * chartWidth;
    const y = chartHeight - ((val - minVal) / (maxVal - minVal)) * chartHeight;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div className="flex justify-between items-end gap-4">
      <svg
        width={chartWidth}
        height={chartHeight}
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        className="border border-border rounded bg-bg"
      >
        <polyline
          points={points}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-brand-green"
        />
        <line x1="0" y1={chartHeight - ((100 - minVal) / (maxVal - minVal)) * chartHeight} x2={chartWidth} y2={chartHeight - ((100 - minVal) / (maxVal - minVal)) * chartHeight} stroke="currentColor" strokeWidth="0.5" className="text-tx-muted opacity-30" />
      </svg>
      <div className="text-right">
        <div className="text-[10px] text-tx-muted mb-1">Start</div>
        <div className="font-mono text-xs font-bold text-tx">$100</div>
        <div className="text-[10px] text-tx-muted mt-2 mb-1">End</div>
        <div className={clsx("font-mono text-xs font-bold", data[data.length - 1] >= 100 ? "text-brand-green" : "text-brand-red")}>
          ${data[data.length - 1].toFixed(2)}
        </div>
      </div>
    </div>
  );
}
