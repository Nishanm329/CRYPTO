import { useState } from "react";
import useSWR from "swr";
import clsx from "clsx";
import { api, formatPrice, formatVolume } from "../lib/api";

const PRESETS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX"];

export default function LiquidationView({ defaultSymbol = "BTC" }) {
  const [symbol, setSymbol] = useState((defaultSymbol || "BTC").replace("USDT", "").toUpperCase());

  const { data, error, isLoading } = useSWR(
    `liquidations-${symbol}`,
    () => api.liquidations(symbol),
    { refreshInterval: 60000, revalidateOnFocus: false }
  );

  const mark = data?.mark_price;
  const levels = data?.levels ?? [];
  // Above current price = short liquidations (squeeze fuel, green);
  // below = long liquidations (downside magnets, red).
  const peakUsd = Math.max(
    1,
    ...levels.map((l) => Math.max(l.long_usd ?? 0, l.short_usd ?? 0))
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 border-b border-border px-5 py-3">
        <h1 className="text-sm font-bold text-tx">Liquidation Heatmap</h1>
        <p className="text-xs text-tx-muted mt-0.5">
          Estimated liquidation clusters from open interest &amp; leverage tiers — a model, not exchange data.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-4 sm:p-5 flex flex-col gap-4 max-w-3xl mx-auto w-full">
        {/* Symbol selector */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar -mx-1 px-1">
          {PRESETS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={clsx(
                "shrink-0 min-w-[52px] px-3 py-2 md:py-1.5 rounded-lg text-xs font-semibold transition-all",
                symbol === s ? "bg-brand-blue text-white" : "bg-bg-card/60 text-tx-muted hover:text-tx active:bg-border"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {error && (
          <div className="text-center py-12 text-tx-muted border border-border border-dashed rounded-xl">
            <div className="text-xs font-medium text-tx mb-1">No perpetual market for {symbol}</div>
            <div className="text-xs text-tx-muted">Try a major pair like BTC, ETH or SOL.</div>
          </div>
        )}

        {!error && isLoading && !data && (
          <div className="text-center py-12 text-tx-muted text-xs">Loading {symbol} liquidation map…</div>
        )}

        {!error && data && (
          <>
            {/* Headline magnets */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-bg-card border border-border rounded-xl p-3">
                <div className="text-[11px] text-tx-muted mb-1">Upside magnet (short squeeze)</div>
                <div className="text-lg font-bold font-mono text-brand-green">
                  {data.magnet_up ? formatPrice(data.magnet_up.price, symbol) : "—"}
                </div>
                <div className="text-[11px] text-tx-muted">{data.magnet_up ? `${formatVolume(data.magnet_up.usd)} est.` : ""}</div>
              </div>
              <div className="bg-bg-card border border-border rounded-xl p-3">
                <div className="text-[11px] text-tx-muted mb-1">Downside magnet (long liq)</div>
                <div className="text-lg font-bold font-mono text-brand-red">
                  {data.magnet_down ? formatPrice(data.magnet_down.price, symbol) : "—"}
                </div>
                <div className="text-[11px] text-tx-muted">{data.magnet_down ? `${formatVolume(data.magnet_down.usd)} est.` : ""}</div>
              </div>
            </div>

            {/* Ladder heatmap */}
            <div className="bg-bg-card border border-border rounded-xl p-3 flex flex-col">
              <div className="flex items-center justify-between text-[10px] text-tx-muted mb-2 px-1">
                <span>← Long liquidations</span>
                <span className="font-mono">OI {data.oi_notional != null ? formatVolume(data.oi_notional) : "—"}</span>
                <span>Short liquidations →</span>
              </div>
              <div className="flex flex-col">
                {levels.map((lv, i) => {
                  const isMark = mark != null && i < levels.length - 1 &&
                    lv.price > mark && levels[i + 1].price <= mark;
                  const longW = ((lv.long_usd ?? 0) / peakUsd) * 100;
                  const shortW = ((lv.short_usd ?? 0) / peakUsd) * 100;
                  return (
                    <div key={i}>
                      <div className="flex items-center gap-1 h-[7px]">
                        {/* left half: long liqs grow leftward */}
                        <div className="flex-1 flex justify-end">
                          <div className="h-[6px] rounded-l-sm bg-brand-red/80" style={{ width: `${longW}%` }} />
                        </div>
                        <div className="w-[58px] shrink-0 text-center text-[9px] font-mono text-tx-muted leading-none">
                          {formatPrice(lv.price, symbol)}
                        </div>
                        {/* right half: short liqs grow rightward */}
                        <div className="flex-1 flex justify-start">
                          <div className="h-[6px] rounded-r-sm bg-brand-green/80" style={{ width: `${shortW}%` }} />
                        </div>
                      </div>
                      {isMark && (
                        <div className="flex items-center gap-2 my-0.5">
                          <div className="flex-1 h-px bg-brand-blue/60" />
                          <span className="text-[9px] font-mono font-bold text-brand-blue shrink-0">
                            {formatPrice(mark, symbol)} now
                          </span>
                          <div className="flex-1 h-px bg-brand-blue/60" />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <p className="text-[10px] text-tx-muted leading-relaxed px-1">
              Estimated by spreading current open interest across common leverage tiers (5–100×) over a volume-weighted map of recent prices.
              Clusters flag zones where stops &amp; liquidations tend to pool — treat as structure, not precise levels.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
