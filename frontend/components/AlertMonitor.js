import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { readAlerts, writeAlerts, ALERTS_EVENT } from "../lib/alerts";

// Polls live prices for every active alert while the app is open. When a price
// crosses an alert's target it marks the alert triggered and fires both a
// browser Notification (if the user granted permission) and an in-app toast.
const POLL_MS = 20000;

export default function AlertMonitor() {
  const [alerts, setAlerts] = useState([]);
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    setAlerts(readAlerts());
    const onChange = (e) => setAlerts(e.detail ?? readAlerts());
    const onStorage = () => setAlerts(readAlerts());
    window.addEventListener(ALERTS_EVENT, onChange);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(ALERTS_EVENT, onChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const activeSymbols = [...new Set(alerts.filter((a) => !a.triggered).map((a) => a.symbol))];
  const symbolKey = activeSymbols.join(",");

  const fire = useCallback((alert, price) => {
    const name = alert.symbol.replace("USDT", "");
    const dir = alert.condition === "above" ? "rose above" : "fell below";
    const message = `${name} ${dir} $${alert.price.toLocaleString()} (now $${price.toLocaleString()})`;

    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      try { new Notification("Price alert", { body: message, tag: `alert-${alert.id}` }); } catch {}
    }

    const id = `${alert.id}-${Date.now()}`;
    setToasts((t) => [...t, { id, message }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 9000);
  }, []);

  useEffect(() => {
    if (!symbolKey) return;
    let cancelled = false;

    const check = async () => {
      try {
        const data = await api.tickers(symbolKey);
        if (cancelled || !data) return;
        let changed = false;
        const next = readAlerts().map((a) => {
          if (a.triggered) return a;
          const px = data[a.symbol]?.price;
          if (px == null) return a;
          const hit = a.condition === "above" ? px >= a.price : px <= a.price;
          if (!hit) return a;
          changed = true;
          fire(a, px);
          return { ...a, triggered: true, triggeredAt: Date.now() };
        });
        if (changed) writeAlerts(next);
      } catch {}
    };

    check();
    const id = setInterval(check, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [symbolKey, fire]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 z-[60] flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="bg-bg-card border border-brand-amber/40 rounded-lg p-3 shadow-lg flex items-start gap-2 animate-in fade-in slide-in-from-bottom-2 duration-300"
        >
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" className="text-brand-amber shrink-0 mt-0.5">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          <span className="text-xs font-medium text-tx flex-1">{t.message}</span>
          <button
            onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}
            className="text-tx-muted hover:text-tx transition-colors shrink-0"
            aria-label="Dismiss"
          >
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
