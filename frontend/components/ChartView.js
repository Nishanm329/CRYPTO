import { useState } from "react";
import useSWR from "swr";
import TradingChart from "./TradingChart";
import { api } from "../lib/api";
import clsx from "clsx";

const TFS = ["1m","5m","15m","1h","4h","1d","3d","1w"];
const POPULAR = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT"];

export default function ChartView({ defaultSymbol = "BTCUSDT" }) {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [timeframe, setTimeframe] = useState("1h");
  const [query, setQuery] = useState("");

  const { data: pairs } = useSWR("pairs", api.pairs, { revalidateOnFocus: false });
  const { data: chartData, isLoading } = useSWR(
    `chart-${symbol}-${timeframe}`,
    () => api.chart(symbol, timeframe, 300),
    { refreshInterval: 30000, revalidateOnFocus: false }
  );

  const allPairs = pairs?.pairs ?? POPULAR;
  const filtered = query
    ? allPairs.filter(p => p.toLowerCase().includes(query.toLowerCase())).slice(0, 20)
    : POPULAR;

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: symbol list */}
      <div className="w-44 shrink-0 border-r border-border flex flex-col bg-bg-sidebar">
        <div className="p-2">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search pair…"
            className="w-full bg-bg border border-border rounded-lg px-2.5 py-1.5 text-xs text-tx placeholder-tx-muted outline-none focus:border-brand-blue transition-colors"
          />
        </div>
        <div className="flex-1 overflow-y-auto no-scrollbar px-1 pb-2">
          {filtered.map(p => (
            <button
              key={p}
              onClick={() => setSymbol(p)}
              className={clsx(
                "w-full text-left px-2.5 py-2 rounded-lg text-xs font-semibold transition-all mb-0.5",
                symbol === p ? "bg-brand-blue/15 text-brand-blue" : "text-tx-muted hover:text-tx hover:bg-border/30"
              )}
            >
              {p.replace("USDT","")}<span className="text-tx-dim font-normal">/USDT</span>
            </button>
          ))}
        </div>
      </div>

      {/* Right: chart */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* TF bar */}
        <div className="h-10 shrink-0 border-b border-border flex items-center px-4 gap-4">
          <span className="text-sm font-bold text-tx">{symbol.replace("USDT","")}<span className="text-tx-muted font-normal">/USDT</span></span>
          <div className="flex gap-0.5">
            {TFS.map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={clsx(
                  "px-2.5 py-1 rounded text-xs font-semibold transition-all",
                  timeframe === tf ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
                )}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 min-h-0">
          <TradingChart chartData={chartData} loading={isLoading} />
        </div>
      </div>
    </div>
  );
}
