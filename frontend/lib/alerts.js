import { useState, useEffect, useCallback } from "react";

// Shared price-alert store (localStorage). Both AlertsView and the global
// AlertMonitor read/write through here so a price-triggered update made by the
// monitor is reflected live in the list, and vice-versa.
const KEY = "price_alerts";
const EVENT = "cs-alerts-change";

export function readAlerts() {
  if (typeof window === "undefined") return [];
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

export function writeAlerts(list) {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY, JSON.stringify(list));
  window.dispatchEvent(new CustomEvent(EVENT, { detail: list }));
}

export function useAlerts() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    setAlerts(readAlerts());
    const onChange = (e) => setAlerts(e.detail ?? readAlerts());
    const onStorage = (e) => { if (e.key === KEY) setAlerts(readAlerts()); };
    window.addEventListener(EVENT, onChange);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(EVENT, onChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const add = useCallback((alert) => {
    writeAlerts([...readAlerts(), { ...alert, id: Date.now(), triggered: false }]);
  }, []);
  const remove = useCallback((id) => {
    writeAlerts(readAlerts().filter((a) => a.id !== id));
  }, []);
  const toggle = useCallback((id) => {
    writeAlerts(readAlerts().map((a) => (a.id === id ? { ...a, triggered: !a.triggered } : a)));
  }, []);

  return { alerts, add, remove, toggle };
}

export const ALERTS_EVENT = EVENT;
export const ALERTS_KEY = KEY;
