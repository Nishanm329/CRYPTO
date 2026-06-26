import { useState, useEffect } from "react";
import useSWR from "swr";
import { api } from "../lib/api";
import { useAlerts } from "../lib/alerts";
import Toast from "./Toast";
import clsx from "clsx";

const POPULAR = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT"];

export default function AlertsView() {
  const { alerts, add, remove, toggle } = useAlerts();
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [condition, setCondition] = useState("above");
  const [price, setPrice] = useState("");
  const [note, setNote] = useState("");
  const [deletedAlert, setDeletedAlert] = useState(null);
  const [showUndo, setShowUndo] = useState(false);
  const [notifPerm, setNotifPerm] = useState("default");

  useEffect(() => {
    if (typeof Notification !== "undefined") setNotifPerm(Notification.permission);
  }, []);

  const enableNotifications = async () => {
    if (typeof Notification === "undefined") return;
    try {
      const perm = await Notification.requestPermission();
      setNotifPerm(perm);
    } catch {}
  };

  const { data: tickerData } = useSWR(
    "alerts-tickers",
    () => api.tickers(POPULAR.join(",")),
    { refreshInterval: 15000 }
  );

  const currentPrice = tickerData?.[symbol]?.price;

  const handleAdd = () => {
    if (!price || isNaN(parseFloat(price))) return;
    add({ symbol, condition, price: parseFloat(price), note, createdAt: Date.now() });
    setPrice(""); setNote("");
  };

  const handleDelete = (id, alert) => {
    remove(id);
    setDeletedAlert(alert);
    setShowUndo(true);
  };

  const handleUndo = () => {
    add(deletedAlert);
    setShowUndo(false);
  };

  return (
    <>
      {showUndo && (
        <Toast
          message={`Alert for ${deletedAlert?.symbol.replace("USDT", "")} deleted`}
          action="Undo"
          onAction={handleUndo}
          type="default"
        />
      )}
      <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 border-b border-border px-5 py-3 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-sm font-bold text-tx">Price Alerts</h1>
          <p className="text-xs text-tx-muted mt-0.5">Get notified when a coin hits your target price.</p>
        </div>
        {notifPerm === "granted" ? (
          <span className="shrink-0 flex items-center gap-1.5 text-[11px] font-semibold text-brand-green">
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.4"><polyline points="20 6 9 17 4 12" /></svg>
            Notifications on
          </span>
        ) : notifPerm === "denied" ? (
          <span className="shrink-0 text-[11px] text-tx-muted">Notifications blocked in browser</span>
        ) : (
          <button
            onClick={enableNotifications}
            className="shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-brand-blue/10 text-brand-blue hover:bg-brand-blue/20 transition-colors"
          >
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" /></svg>
            Enable notifications
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-5 flex flex-col gap-5 max-w-2xl mx-auto w-full">
        {/* Create alert */}
        <div className="bg-bg-card border border-border rounded-xl p-4">
          <div className="text-xs font-semibold text-tx mb-3">Create Alert</div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">Coin</label>
              <select
                value={symbol}
                onChange={e => setSymbol(e.target.value)}
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx outline-none focus:border-brand-blue transition-colors"
              >
                {POPULAR.map(p => <option key={p} value={p}>{p.replace("USDT","")}/USDT</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">Condition</label>
              <select
                value={condition}
                onChange={e => setCondition(e.target.value)}
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx outline-none focus:border-brand-blue transition-colors"
              >
                <option value="above">Price goes above</option>
                <option value="below">Price goes below</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">
                Target Price {currentPrice && <span className="text-tx-dim">(now ${currentPrice?.toLocaleString()})</span>}
              </label>
              <input
                type="number"
                value={price}
                onChange={e => setPrice(e.target.value)}
                placeholder="e.g. 100000"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx placeholder-tx-muted outline-none focus:border-brand-blue transition-colors"
              />
            </div>
            <div>
              <label className="text-[10px] text-tx-muted uppercase tracking-wider mb-1 block">Note (optional)</label>
              <input
                value={note}
                onChange={e => setNote(e.target.value)}
                placeholder="e.g. ATH breakout"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-tx placeholder-tx-muted outline-none focus:border-brand-blue transition-colors"
              />
            </div>
          </div>
          <button
            onClick={handleAdd}
            disabled={!price}
            className={clsx(
              "mt-3 w-full py-2 rounded-lg text-xs font-bold transition-all",
              price ? "bg-brand-blue text-white hover:bg-blue-500" : "bg-bg text-tx-muted cursor-not-allowed border border-border"
            )}
          >
            + Add Alert
          </button>
        </div>

        {/* Alert list */}
        <div>
          <div className="text-xs font-semibold text-tx mb-2">Active Alerts ({alerts.length})</div>
          {alerts.length === 0 ? (
            <div className="text-center py-12 text-tx-muted border border-border border-dashed rounded-xl">
              <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="mx-auto mb-3 opacity-50">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              <div className="text-xs font-medium text-tx mb-1">No active alerts</div>
              <div className="text-xs text-tx-muted">Create your first price alert above →</div>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {alerts.map(a => (
                <div
                  key={a.id}
                  className={clsx(
                    "flex items-center gap-3 p-3 rounded-xl border transition-all",
                    a.triggered ? "bg-brand-green/5 border-brand-green/20" : "bg-bg-card border-border"
                  )}
                >
                  <div className={clsx(
                    "w-2 h-2 rounded-full shrink-0",
                    a.triggered ? "bg-brand-green" : "bg-brand-amber animate-pulse"
                  )} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-tx">{a.symbol.replace("USDT","")}/USDT</span>
                      <span className="text-xs text-tx-muted">{a.condition === "above" ? "↑ above" : "↓ below"}</span>
                      <span className="text-xs font-bold font-mono text-brand-amber">${a.price?.toLocaleString()}</span>
                    </div>
                    {a.note && <div className="text-[10px] text-tx-muted mt-0.5">{a.note}</div>}
                    <div className="text-[10px] text-tx-dim mt-0.5">{new Date(a.createdAt).toLocaleDateString()}</div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => toggle(a.id)}
                      className={clsx(
                        "text-[10px] px-2 py-0.5 rounded border font-medium transition-all",
                        a.triggered
                          ? "border-brand-green/30 text-brand-green"
                          : "border-border text-tx-muted hover:border-border-light"
                      )}
                    >
                      {a.triggered ? "Triggered" : "Active"}
                    </button>
                    <button
                      onClick={() => handleDelete(a.id, a)}
                      className="p-1 rounded text-tx-muted hover:text-brand-red hover:bg-brand-red/10 transition-all"
                    >
                      <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      </div>
    </>
  );
}
