import { useState } from "react";
import useSWR from "swr";
import clsx from "clsx";
import { tradingApi, formatTrade } from "../lib/trading-api";
import { formatPrice } from "../lib/api";

export default function TradeHistoryView() {
  const [symbol, setSymbol] = useState(null);
  const { data, error, isLoading } = useSWR("/api/trading/history", async (url) => {
    try {
      const response = await fetch(url, {
        headers: {
          "Authorization": `Bearer ${process.env.NEXT_PUBLIC_API_KEY || "demo-key-public"}`,
        },
      });
      if (!response.ok) throw new Error("Failed to fetch history");
      return await response.json();
    } catch (err) {
      console.error("Error fetching history:", err);
      return { history: [], count: 0, performance: {} };
    }
  }, { revalidateOnFocus: false });

  const history = data?.history || [];
  const perf = data?.performance || {};

  const filteredHistory = symbol ? history.filter(t => t.symbol === symbol) : history;
  const symbols = [...new Set(history.map(t => t.symbol))];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 border-b border-border px-5 py-3">
        <h1 className="text-sm font-bold text-tx">Trade History</h1>
        <p className="text-xs text-tx-muted mt-0.5">View your closed trades and performance metrics.</p>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-5 max-w-5xl mx-auto w-full">
        {/* Performance Stats */}
        {perf && Object.keys(perf).length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <StatCard label="Total Trades" value={perf.total_trades || 0} />
            <StatCard label="Win Rate" value={`${(perf.win_rate || 0).toFixed(1)}%`} />
            <StatCard label="Profit Factor" value={(perf.profit_factor || 0).toFixed(2)} />
            <StatCard
              label="Total P&L"
              value={`$${(perf.total_pnl || 0).toFixed(2)}`}
              color={(perf.total_pnl || 0) >= 0 ? "#22c55e" : "#ef4444"}
            />
          </div>
        )}

        {/* Filter by Symbol */}
        {symbols.length > 0 && (
          <div className="mb-4 flex gap-2 flex-wrap">
            <button
              onClick={() => setSymbol(null)}
              className={clsx(
                "text-xs px-3 py-1.5 rounded-lg border transition-all",
                !symbol
                  ? "bg-brand-blue border-brand-blue text-white"
                  : "border-border text-tx-muted hover:border-border-light"
              )}
            >
              All ({history.length})
            </button>
            {symbols.map(sym => (
              <button
                key={sym}
                onClick={() => setSymbol(sym)}
                className={clsx(
                  "text-xs px-3 py-1.5 rounded-lg border transition-all",
                  symbol === sym
                    ? "bg-brand-blue border-brand-blue text-white"
                    : "border-border text-tx-muted hover:border-border-light"
                )}
              >
                {sym} ({filteredHistory.filter(t => t.symbol === sym).length})
              </button>
            ))}
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="text-xs text-tx-muted text-center py-8">Loading trade history...</div>
        )}

        {/* Empty State */}
        {!isLoading && filteredHistory.length === 0 && (
          <div className="text-xs text-tx-muted text-center py-8">
            {symbol ? "No trades found for this symbol" : "No closed trades yet"}
          </div>
        )}

        {/* Desktop Table View */}
        {!isLoading && filteredHistory.length > 0 && (
          <div className="hidden md:block overflow-x-auto bg-bg-card border border-border rounded-xl">
            <table className="w-full text-xs">
              <thead className="bg-bg border-b border-border/50">
                <tr className="text-tx-muted">
                  <th className="text-left py-3 px-4 font-semibold">Pair</th>
                  <th className="text-left py-3 px-4 font-semibold">Entry</th>
                  <th className="text-left py-3 px-4 font-semibold">Exit</th>
                  <th className="text-right py-3 px-4 font-semibold">Qty</th>
                  <th className="text-right py-3 px-4 font-semibold">P&L</th>
                  <th className="text-right py-3 px-4 font-semibold">%</th>
                  <th className="text-center py-3 px-4 font-semibold">Duration</th>
                  <th className="text-center py-3 px-4 font-semibold">Reason</th>
                </tr>
              </thead>
              <tbody>
                {filteredHistory.map((trade) => {
                  const formatted = formatTrade(trade);
                  return (
                    <tr key={trade.id} className="border-b border-border/30 hover:bg-bg/50 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className={clsx(
                            "text-xs font-bold px-1.5 py-0.5 rounded",
                            trade.direction === "LONG"
                              ? "bg-brand-green/20 text-brand-green"
                              : "bg-brand-red/20 text-brand-red"
                          )}>
                            {trade.direction === "LONG" ? "▲" : "▼"}
                          </span>
                          <span className="font-bold text-tx">{trade.symbol}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 font-mono text-tx">${formatPrice(trade.entry_price)}</td>
                      <td className="py-3 px-4 font-mono text-tx">${formatPrice(trade.exit_price)}</td>
                      <td className="py-3 px-4 font-mono text-tx-muted text-right">{trade.quantity.toFixed(4)}</td>
                      <td className="py-3 px-4 font-mono font-bold text-right" style={{ color: formatted.pnlColor }}>
                        ${trade.realized_pnl.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-right" style={{ color: formatted.pnlColor }}>
                        {trade.realized_pnl_pct >= 0 ? "+" : ""}{trade.realized_pnl_pct.toFixed(2)}%
                      </td>
                      <td className="py-3 px-4 text-center text-tx-muted">
                        {trade.duration_hours < 1 ? "<1h" : `${(trade.duration_hours / 24).toFixed(1)}d`}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={clsx(
                          "text-xs px-2 py-1 rounded-full font-semibold",
                          trade.exit_reason === "TP1" || trade.exit_reason === "TP2" || trade.exit_reason === "TP3"
                            ? "bg-brand-green/20 text-brand-green"
                            : "bg-brand-red/20 text-brand-red"
                        )}>
                          {trade.exit_reason || "—"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Mobile Card View */}
        {!isLoading && filteredHistory.length > 0 && (
          <div className="md:hidden space-y-3">
            {filteredHistory.map((trade) => {
              const formatted = formatTrade(trade);
              return (
                <div
                  key={trade.id}
                  className="bg-bg-card border border-border rounded-lg p-4"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <span className={clsx(
                        "text-xs font-bold px-2 py-0.5 rounded mr-2",
                        trade.direction === "LONG"
                          ? "bg-brand-green/20 text-brand-green"
                          : "bg-brand-red/20 text-brand-red"
                      )}>
                        {trade.direction === "LONG" ? "▲ LONG" : "▼ SHORT"}
                      </span>
                      <span className="text-sm font-bold text-tx">{trade.symbol}</span>
                    </div>
                    <span className="text-sm font-bold" style={{ color: formatted.pnlColor }}>
                      {trade.realized_pnl >= 0 ? "+" : ""}{trade.realized_pnl.toFixed(2)} USD
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-3 text-xs">
                    <div>
                      <div className="text-tx-muted">Entry</div>
                      <div className="font-mono text-tx font-bold">${formatPrice(trade.entry_price)}</div>
                    </div>
                    <div>
                      <div className="text-tx-muted">Exit</div>
                      <div className="font-mono text-tx font-bold">${formatPrice(trade.exit_price)}</div>
                    </div>
                    <div>
                      <div className="text-tx-muted">Return</div>
                      <div className="font-mono font-bold" style={{ color: formatted.pnlColor }}>
                        {trade.realized_pnl_pct >= 0 ? "+" : ""}{trade.realized_pnl_pct.toFixed(2)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-tx-muted">Duration</div>
                      <div className="text-tx font-mono">
                        {trade.duration_hours < 1 ? "<1h" : `${(trade.duration_hours / 24).toFixed(1)}d`}
                      </div>
                    </div>
                  </div>

                  <div className="text-xs text-center text-tx-muted">
                    Exit: {trade.exit_reason || "Manual"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color = "#fff" }) {
  return (
    <div className="bg-bg-card border border-border rounded-lg p-3">
      <div className="text-[10px] text-tx-muted uppercase tracking-widest mb-1">{label}</div>
      <div className="text-lg font-bold" style={{ color }}>{value}</div>
    </div>
  );
}
