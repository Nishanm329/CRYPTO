import { useState, useEffect } from "react";
import useSWR from "swr";
import clsx from "clsx";
import { tradingApi, formatTrade } from "../lib/trading-api";
import { formatPrice } from "../lib/api";

export default function OpenOrdersPanel() {
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [tradingMode, setTradingMode] = useState("PAPER");
  const [closingTrade, setClosingTrade] = useState(false);
  const [closeError, setCloseError] = useState(null);

  // Fetch trading mode on mount
  useEffect(() => {
    const fetchTradingSettings = async () => {
      try {
        const status = await tradingApi.getKeysStatus();
        if (status && status.trading_mode) {
          setTradingMode(status.trading_mode);
        }
      } catch (err) {
        console.warn("Failed to fetch trading mode, defaulting to PAPER:", err);
        setTradingMode("PAPER");
      }
    };

    fetchTradingSettings();
  }, []);

  const { data, error, isLoading, mutate } = useSWR("/api/trading/orders", async (url) => {
    try {
      const response = await fetch(url, {
        headers: {
          "Authorization": `Bearer ${process.env.NEXT_PUBLIC_API_KEY || "demo-key-public"}`,
        },
      });
      if (!response.ok) throw new Error("Failed to fetch orders");
      return await response.json();
    } catch (err) {
      console.error("Error fetching orders:", err);
      return { orders: [], count: 0 };
    }
  }, {
    refreshInterval: 10000, // Refresh every 10 seconds
    revalidateOnFocus: false,
  });

  const orders = data?.orders || [];

  const handleCloseTrade = async () => {
    if (!selectedTrade) return;

    setClosingTrade(true);
    setCloseError(null);

    try {
      const response = await fetch("/api/trading/close", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${process.env.NEXT_PUBLIC_API_KEY || "demo-key-public"}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          trade_id: selectedTrade.id,
          exit_price: null,  // Market close
          exit_reason: "MANUAL_EXIT",
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        setCloseError(error.detail || "Failed to close trade");
        return;
      }

      const result = await response.json();

      // Close modal and refresh trades
      setSelectedTrade(null);
      mutate();  // Refresh the orders list

      // Show success message
      console.log("Trade closed successfully:", result);
    } catch (err) {
      setCloseError(err.message || "Failed to close trade");
    } finally {
      setClosingTrade(false);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-bg-card border border-border rounded-xl p-4">
        <div className="text-xs font-semibold text-tx-muted uppercase tracking-widest mb-4">Open Orders</div>
        <div className="text-xs text-tx-muted text-center py-8">Loading trades...</div>
      </div>
    );
  }

  if (!orders.length) {
    return (
      <div className="bg-bg-card border border-border rounded-xl p-4">
        <div className="text-xs font-semibold text-tx-muted uppercase tracking-widest mb-4">Open Orders</div>
        <div className="text-xs text-tx-muted text-center py-8">No open trades yet</div>
      </div>
    );
  }

  return (
    <div className="bg-bg-card border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-tx-muted uppercase tracking-widest">Open Orders</span>
            {tradingMode === "PAPER" && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                [SIMULATED]
              </span>
            )}
            {tradingMode === "LIVE" && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-brand-red/20 text-brand-red">
                [LIVE]
              </span>
            )}
          </div>
          <div className="text-[10px] text-tx-muted mt-0.5">{orders.length} active {orders.length === 1 ? "trade" : "trades"}</div>
        </div>
        <button
          onClick={() => mutate()}
          className="text-xs text-tx-muted hover:text-tx transition-colors"
          title="Refresh"
        >
          ↻
        </button>
      </div>

      {/* Table for larger screens */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-tx-muted border-b border-border/50">
            <tr>
              <th className="text-left py-2 px-2 font-semibold">Pair</th>
              <th className="text-left py-2 px-2 font-semibold">Entry</th>
              <th className="text-right py-2 px-2 font-semibold">Current</th>
              <th className="text-right py-2 px-2 font-semibold">Qty</th>
              <th className="text-right py-2 px-2 font-semibold">P&L</th>
              <th className="text-right py-2 px-2 font-semibold">%</th>
              <th className="text-center py-2 px-2 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((trade) => {
              const formatted = formatTrade(trade);
              const isWinning = formatted.isWinning;
              return (
                <tr
                  key={trade.id}
                  className="border-b border-border/30 hover:bg-bg/50 transition-colors cursor-pointer"
                  onClick={() => setSelectedTrade(trade)}
                >
                  <td className="py-3 px-2">
                    <div className="flex items-center gap-2">
                      <span className={clsx(
                        "text-xs font-bold px-1.5 py-0.5 rounded",
                        trade.direction === "LONG"
                          ? "bg-brand-green/20 text-brand-green"
                          : "bg-brand-red/20 text-brand-red"
                      )}>
                        {trade.direction === "LONG" ? "▲" : "▼"}
                      </span>
                      <div>
                        <span className="font-bold text-tx block">{trade.symbol}</span>
                        {tradingMode === "PAPER" && (
                          <span className="text-[10px] text-yellow-400">[SIMULATED]</span>
                        )}
                        {tradingMode === "LIVE" && (
                          <span className="text-[10px] text-brand-red">[LIVE]</span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-2 font-mono text-tx">${formatPrice(trade.entry_price)}</td>
                  <td className="py-3 px-2 font-mono text-tx text-right">${formatPrice(trade.current_price)}</td>
                  <td className="py-3 px-2 font-mono text-tx-muted text-right">{trade.quantity.toFixed(4)}</td>
                  <td className="py-3 px-2 font-mono font-bold text-right" style={{ color: formatted.pnlColor }}>
                    ${trade.unrealized_pnl.toFixed(2)}
                  </td>
                  <td className="py-3 px-2 font-mono font-bold text-right" style={{ color: formatted.pnlColor }}>
                    {trade.unrealized_pnl_pct >= 0 ? "+" : ""}{trade.unrealized_pnl_pct.toFixed(2)}%
                  </td>
                  <td className="py-3 px-2 text-center">
                    <button
                      className="text-xs text-brand-blue hover:text-blue-400 transition-colors font-semibold"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedTrade(trade);
                      }}
                    >
                      Close
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Card view for mobile */}
      <div className="md:hidden space-y-3">
        {orders.map((trade) => {
          const formatted = formatTrade(trade);
          return (
            <div
              key={trade.id}
              onClick={() => setSelectedTrade(trade)}
              className="bg-bg rounded-lg p-3 border border-border cursor-pointer hover:border-border-light transition-all"
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <span className={clsx(
                    "text-xs font-bold px-2 py-0.5 rounded mr-2",
                    trade.direction === "LONG"
                      ? "bg-brand-green/20 text-brand-green"
                      : "bg-brand-red/20 text-brand-red"
                  )}>
                    {trade.direction === "LONG" ? "▲ LONG" : "▼ SHORT"}
                  </span>
                  <div>
                    <span className="text-sm font-bold text-tx block">{trade.symbol}</span>
                    {tradingMode === "PAPER" && (
                      <span className="text-[10px] text-yellow-400">[SIMULATED]</span>
                    )}
                    {tradingMode === "LIVE" && (
                      <span className="text-[10px] text-brand-red">[LIVE]</span>
                    )}
                  </div>
                </div>
                <span className="text-sm font-bold" style={{ color: formatted.pnlColor }}>
                  {trade.unrealized_pnl >= 0 ? "+" : ""}{trade.unrealized_pnl.toFixed(2)} USD
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                <div>
                  <div className="text-tx-muted">Entry</div>
                  <div className="font-mono text-tx">${formatPrice(trade.entry_price)}</div>
                </div>
                <div>
                  <div className="text-tx-muted">Current</div>
                  <div className="font-mono text-tx">${formatPrice(trade.current_price)}</div>
                </div>
                <div>
                  <div className="text-tx-muted">P&L %</div>
                  <div className="font-mono font-bold" style={{ color: formatted.pnlColor }}>
                    {trade.unrealized_pnl_pct >= 0 ? "+" : ""}{trade.unrealized_pnl_pct.toFixed(2)}%
                  </div>
                </div>
              </div>
              <button
                className="w-full text-xs text-brand-blue hover:text-blue-400 font-semibold py-1.5 rounded border border-brand-blue/30 hover:border-brand-blue transition-all"
              >
                Close Trade
              </button>
            </div>
          );
        })}
      </div>

      {/* Close Trade Modal */}
      {selectedTrade && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-bg-card border border-border rounded-2xl p-6 max-w-sm w-full mx-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-tx">Close Trade</h2>
              <button
                onClick={() => setSelectedTrade(null)}
                className="text-tx-muted hover:text-tx text-2xl leading-none"
              >
                ✕
              </button>
            </div>

            <div className="bg-bg rounded-lg p-4 mb-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-tx-muted">Symbol</span>
                <span className="text-sm font-bold text-tx">{selectedTrade.symbol}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-tx-muted">Entry Price</span>
                <span className="text-sm font-mono text-tx">${formatPrice(selectedTrade.entry_price)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-tx-muted">Current Price</span>
                <span className="text-sm font-mono text-tx">${formatPrice(selectedTrade.current_price)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-tx-muted">Unrealized P&L</span>
                <span className="text-sm font-bold" style={{ color: selectedTrade.unrealized_pnl_pct >= 0 ? "#22c55e" : "#ef4444" }}>
                  {selectedTrade.unrealized_pnl >= 0 ? "+" : ""}{selectedTrade.unrealized_pnl.toFixed(2)} USD
                </span>
              </div>
            </div>

            {closeError && (
              <div className="bg-brand-red/20 border border-brand-red/40 rounded-lg p-3 mb-4 text-xs text-brand-red">
                {closeError}
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => setSelectedTrade(null)}
                disabled={closingTrade}
                className="flex-1 px-4 py-2.5 rounded-lg border border-border text-xs font-semibold text-tx hover:border-border-light transition-all disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCloseTrade}
                disabled={closingTrade}
                className="flex-1 px-4 py-2.5 rounded-lg bg-brand-red hover:bg-red-500 text-white text-xs font-bold transition-all disabled:opacity-50"
              >
                {closingTrade ? "Closing..." : "Close Position"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
