import { useState } from "react";
import useSWR from "swr";
import clsx from "clsx";
import { api, formatPrice, formatVolume, formatChange } from "../lib/api";
import { useWatchlist, normalizeSymbol } from "../lib/watchlist";

const PRESETS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "TRX", "DOT", "MATIC"];

function StarIcon({ filled }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

export default function WatchlistView({ onSelectSymbol }) {
  const { list, add, remove } = useWatchlist();
  const [input, setInput] = useState("");

  const symbolsKey = list.join(",");
  const { data, error, isLoading } = useSWR(
    list.length ? `watchlist-tickers-${symbolsKey}` : null,
    () => api.tickers(symbolsKey),
    { refreshInterval: 15000, revalidateOnFocus: false }
  );

  const submit = (e) => {
    e.preventDefault();
    const sym = normalizeSymbol(input);
    if (sym) add(sym);
    setInput("");
  };

  const available = PRESETS.filter((p) => !list.includes(`${p}USDT`));

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 border-b border-border px-5 py-3">
        <h1 className="text-sm font-bold text-tx">Watchlist</h1>
        <p className="text-xs text-tx-muted mt-0.5">Your starred pairs with live 24h prices. Tap a row to open it.</p>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-4 sm:p-5 flex flex-col gap-4 max-w-3xl mx-auto w-full">
        {/* Add bar */}
        <form onSubmit={submit} className="flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Add a symbol (e.g. BTC, SOL)…"
            className="flex-1 min-w-0 bg-bg-card border border-border rounded-lg px-3 py-2 text-xs text-tx placeholder:text-tx-muted focus:outline-none focus:border-brand-blue"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="shrink-0 px-4 py-2 rounded-lg text-xs font-semibold bg-brand-blue text-white disabled:opacity-40 transition-all"
          >
            Add
          </button>
        </form>

        {/* Quick-add presets */}
        {available.length > 0 && (
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar -mx-1 px-1">
            {available.map((p) => (
              <button
                key={p}
                onClick={() => add(p)}
                className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-bg-card/60 text-tx-muted hover:text-tx active:bg-border transition-all"
              >
                + {p}
              </button>
            ))}
          </div>
        )}

        {/* Empty state */}
        {list.length === 0 && (
          <div className="text-center py-12 text-tx-muted border border-border border-dashed rounded-xl">
            <div className="text-xs font-medium text-tx mb-1">Your watchlist is empty</div>
            <div className="text-xs text-tx-muted">Add a symbol above to start tracking it.</div>
          </div>
        )}

        {error && list.length > 0 && (
          <div className="text-center py-8 text-xs text-tx-muted">Couldn’t load prices. Retrying…</div>
        )}

        {/* Rows */}
        <div className="flex flex-col gap-2">
          {list.map((sym) => {
            const t = data?.[sym];
            const base = sym.replace("USDT", "");
            const change = t?.change_24h;
            const up = (change ?? 0) >= 0;
            return (
              <div
                key={sym}
                className="flex items-center gap-3 bg-bg-card border border-border rounded-xl px-3 py-3"
              >
                <button
                  onClick={() => remove(sym)}
                  title="Remove from watchlist"
                  className="shrink-0 text-brand-gold hover:opacity-70 transition-opacity"
                >
                  <StarIcon filled />
                </button>

                <button
                  onClick={() => onSelectSymbol?.(sym)}
                  className="flex-1 min-w-0 text-left"
                >
                  <div className="text-sm font-semibold text-tx truncate">
                    {base}
                    <span className="text-tx-muted font-normal">/USDT</span>
                  </div>
                  <div className="text-[11px] text-tx-muted">
                    {t ? `Vol ${formatVolume(t.volume_24h)}` : isLoading ? "Loading…" : "—"}
                  </div>
                </button>

                <div className="text-right shrink-0">
                  <div className="text-sm font-mono font-bold text-tx">
                    {t ? formatPrice(t.price, sym) : "—"}
                  </div>
                  {change != null && (
                    <div className={clsx("text-[11px] font-mono font-semibold", up ? "text-brand-green" : "text-brand-red")}>
                      {formatChange(change)}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
