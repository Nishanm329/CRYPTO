import { useState, useEffect, useCallback } from "react";

// Persisted in localStorage. A custom event keeps every mounted hook instance
// in sync within the same tab; the native "storage" event syncs across tabs.
const KEY = "cs_watchlist";
const DEFAULT = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];
const EVENT = "cs-watchlist-change";

function read() {
  if (typeof window === "undefined") return DEFAULT;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return DEFAULT;
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : DEFAULT;
  } catch {
    return DEFAULT;
  }
}

function write(list) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
    window.dispatchEvent(new CustomEvent(EVENT, { detail: list }));
  } catch {
    /* storage unavailable (private mode) — keep in-memory only */
  }
}

export function normalizeSymbol(sym) {
  const s = (sym || "").trim().toUpperCase();
  if (!s) return "";
  return s.endsWith("USDT") ? s : `${s}USDT`;
}

export function useWatchlist() {
  const [list, setList] = useState(DEFAULT);

  useEffect(() => {
    setList(read());
    const onCustom = (e) => setList(e.detail ?? read());
    const onStorage = () => setList(read());
    window.addEventListener(EVENT, onCustom);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(EVENT, onCustom);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const add = useCallback((sym) => {
    const s = normalizeSymbol(sym);
    if (!s) return;
    setList((prev) => {
      if (prev.includes(s)) return prev;
      const next = [...prev, s];
      write(next);
      return next;
    });
  }, []);

  const remove = useCallback((sym) => {
    const s = normalizeSymbol(sym);
    setList((prev) => {
      const next = prev.filter((x) => x !== s);
      write(next);
      return next;
    });
  }, []);

  const toggle = useCallback((sym) => {
    const s = normalizeSymbol(sym);
    if (!s) return;
    setList((prev) => {
      const next = prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s];
      write(next);
      return next;
    });
  }, []);

  const isWatched = useCallback((sym) => list.includes(normalizeSymbol(sym)), [list]);

  return { list, add, remove, toggle, isWatched };
}
