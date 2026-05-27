import { useState, useEffect } from "react";
import useSWR from "swr";
import { api } from "../lib/api";
import Toast from "./Toast";
import clsx from "clsx";

function usePortfolio() {
  const [holdings, setHoldings] = useState([]);
  useEffect(() => {
    try { setHoldings(JSON.parse(localStorage.getItem("portfolio") ?? "[]")); } catch {}
  }, []);
  const save = (list) => { setHoldings(list); localStorage.setItem("portfolio", JSON.stringify(list)); };
  const add = (h) => save([...holdings, { ...h, id: Date.now() }]);
  const remove = (id) => save(holdings.filter(h => h.id !== id));
  return { holdings, add, remove };
}

export default function PortfolioView() {
  const { holdings, add, remove } = usePortfolio();
  const [sym, setSym] = useState("BTC");
  const [qty, setQty] = useState("");
  const [avgBuy, setAvgBuy] = useState("");
  const [deletedHolding, setDeletedHolding] = useState(null);
  const [showUndo, setShowUndo] = useState(false);

  const symbols = holdings.map(h => `${h.symbol}USDT`);
  const { data: prices } = useSWR(
    symbols.length ? `portfolio-prices-${symbols.join(",")}` : null,
    () => api.tickers(symbols.join(",")),
    { refreshInterval: 15000 }
  );

  const enriched = holdings.map(h => {
    const tick = prices?.[`${h.symbol}USDT`];
    const currentPrice = tick?.price ?? 0;
    const currentValue = currentPrice * h.qty;
    const costBasis = h.avgBuy * h.qty;
    const pnl = currentValue - costBasis;
    const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;
    return { ...h, currentPrice, currentValue, costBasis, pnl, pnlPct, change24h: tick?.change_24h ?? 0 };
  });

  const totalValue = enriched.reduce((s, h) => s + h.currentValue, 0);
  const totalCost = enriched.reduce((s, h) => s + h.costBasis, 0);
  const totalPnl = totalValue - totalCost;
  const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

  const handleAdd = () => {
    if (!sym || !qty || !avgBuy) return;
    add({ symbol: sym.toUpperCase().replace("USDT",""), qty: parseFloat(qty), avgBuy: parseFloat(avgBuy) });
    setQty(""); setAvgBuy("");
  };

  const handleDelete = (id, holding) => {
    remove(id);
    setDeletedHolding(holding);
    setShowUndo(true);
  };

  const handleUndo = () => {
    add(deletedHolding);
    setShowUndo(false);
  };

  return (
    <>
      {showUndo && (
        <Toast
          message={`${deletedHolding?.symbol} holding removed`}
          action="Undo"
          onAction={handleUndo}
          type="default"
        />
      )}
      <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 border-b border-border px-5 py-3">
        <h1 className="text-sm font-bold text-tx">Portfolio</h1>
        <p className="text-xs text-tx-muted mt-0.5">Track your holdings and P&L in real-time.</p>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-5 flex flex-col gap-5 max-w-3xl mx-auto w-full">
        {/* Summary */}
        {enriched.length > 0 && (
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Total Value", val: `$${totalValue.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}`, cls: "text-tx" },
              { label: "Total P&L", val: `${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`, cls: totalPnl >= 0 ? "text-brand-green" : "text-brand-red" },
              { label: "Return", val: `${totalPnlPct >= 0 ? "+" : ""}${totalPnlPct.toFixed(2)}%`, cls: totalPnlPct >= 0 ? "text-brand-green" : "text-brand-red" },
            ].map(({ label, val, cls }) => (
              <div key={label} className="bg-bg-card border border-border rounded-xl p-4">
                <div className="text-[10px] text-tx-muted mb-1">{label}</div>
                <div className={clsx("text-lg font-bold font-mono", cls)}>{val}</div>
              </div>
            ))}
          </div>
        )}

        {/* Add holding */}
        <div className="bg-bg-card border border-border rounded-xl p-4">
          <div className="text-xs font-semibold text-tx mb-3">Add Holding</div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">Symbol</label>
              <input
                value={sym}
                onChange={e => setSym(e.target.value.toUpperCase())}
                placeholder="BTC"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx placeholder-tx-muted outline-none focus:border-brand-blue transition-colors"
              />
            </div>
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">Quantity</label>
              <input
                type="number"
                value={qty}
                onChange={e => setQty(e.target.value)}
                placeholder="0.5"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx placeholder-tx-muted outline-none focus:border-brand-blue transition-colors"
              />
            </div>
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">Avg Buy Price ($)</label>
              <input
                type="number"
                value={avgBuy}
                onChange={e => setAvgBuy(e.target.value)}
                placeholder="50000"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx placeholder-tx-muted outline-none focus:border-brand-blue transition-colors"
              />
            </div>
          </div>
          <button
            onClick={handleAdd}
            disabled={!sym || !qty || !avgBuy}
            className={clsx(
              "mt-3 w-full py-2 rounded-lg text-xs font-bold transition-all",
              sym && qty && avgBuy ? "bg-brand-blue text-white hover:bg-blue-500" : "bg-bg text-tx-muted cursor-not-allowed border border-border"
            )}
          >
            + Add to Portfolio
          </button>
        </div>

        {/* Holdings table */}
        {enriched.length > 0 ? (
          <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-tx-muted">
                  <th className="py-2.5 pl-4 pr-2 text-left font-medium">Asset</th>
                  <th className="py-2.5 px-2 text-right font-medium">Qty</th>
                  <th className="py-2.5 px-2 text-right font-medium">Avg Buy</th>
                  <th className="py-2.5 px-2 text-right font-medium">Current</th>
                  <th className="py-2.5 px-2 text-right font-medium">Value</th>
                  <th className="py-2.5 px-2 text-right font-medium">P&L</th>
                  <th className="py-2.5 px-2 text-right font-medium">24h</th>
                  <th className="py-2.5 pr-4 px-2 text-right font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {enriched.map(h => (
                  <tr key={h.id} className="border-b border-border/40 hover:bg-border/10 transition-colors">
                    <td className="py-3 pl-4 pr-2">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-blue/30 to-purple-600/30 flex items-center justify-center text-[10px] font-bold text-tx shrink-0">
                          {h.symbol.slice(0,2)}
                        </div>
                        <div>
                          <div className="font-bold text-tx">{h.symbol}</div>
                          <div className="text-[10px] text-tx-muted">USDT</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-2 text-right font-mono text-tx">{h.qty}</td>
                    <td className="py-3 px-2 text-right font-mono text-tx-muted">${h.avgBuy?.toLocaleString()}</td>
                    <td className="py-3 px-2 text-right font-mono text-tx">${h.currentPrice?.toLocaleString()}</td>
                    <td className="py-3 px-2 text-right font-mono font-bold text-tx">${h.currentValue?.toFixed(2)}</td>
                    <td className="py-3 px-2 text-right">
                      <div className={clsx("font-bold font-mono", h.pnl >= 0 ? "text-brand-green" : "text-brand-red")}>
                        {h.pnl >= 0 ? "+" : ""}${h.pnl?.toFixed(2)}
                      </div>
                      <div className={clsx("text-[10px]", h.pnlPct >= 0 ? "text-brand-green" : "text-brand-red")}>
                        {h.pnlPct >= 0 ? "+" : ""}{h.pnlPct?.toFixed(2)}%
                      </div>
                    </td>
                    <td className={clsx("py-3 px-2 text-right font-mono text-xs", h.change24h >= 0 ? "text-brand-green" : "text-brand-red")}>
                      {h.change24h >= 0 ? "+" : ""}{h.change24h?.toFixed(2)}%
                    </td>
                    <td className="py-3 pr-4 px-2 text-right">
                      <button onClick={() => handleDelete(h.id, h)} className="p-1 rounded text-tx-muted hover:text-brand-red hover:bg-brand-red/10 transition-all">
                        <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 text-tx-muted border border-border border-dashed rounded-xl">
            <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="mx-auto mb-3 opacity-50">
              <rect x="2" y="7" width="20" height="14" rx="2" />
              <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
            </svg>
            <div className="text-xs font-medium text-tx mb-1">No holdings yet</div>
            <div className="text-xs text-tx-muted">Add your first position above to start tracking →</div>
          </div>
        )}
      </div>
      </div>
    </>
  );
}
