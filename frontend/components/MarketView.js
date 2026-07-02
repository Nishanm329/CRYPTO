import { useState } from "react";
import useSWR from "swr";
import { api, formatChange } from "../lib/api";
import EmailScheduleButton from "./EmailScheduleButton";
import clsx from "clsx";

const TOP_PAIRS = [
  "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT",
  "DOTUSDT","MATICUSDT","LINKUSDT","UNIUSDT","LTCUSDT","ATOMUSDT","NEARUSDT","APTUSDT",
  "OPUSDT","ARBUSDT","INJUSDT","SUIUSDT","SEIUSDT","TIAUSDT","PYTHUSDT","JUPUSDT",
];

function Sparkbar({ change }) {
  const pos = change >= 0;
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-1.5 bg-bg rounded-full overflow-hidden">
        <div
          className={clsx("h-full rounded-full", pos ? "bg-brand-green" : "bg-brand-red")}
          style={{ width: `${Math.min(100, Math.abs(change) * 10)}%`, marginLeft: pos ? 0 : "auto" }}
        />
      </div>
      <span className={clsx("text-xs font-mono font-bold w-14 text-right", pos ? "text-brand-green" : "text-brand-red")}>
        {pos ? "+" : ""}{change?.toFixed(2)}%
      </span>
    </div>
  );
}

export default function MarketView({ onSelectSymbol }) {
  const [sortKey, setSortKey] = useState("volume");
  const [sortDir, setSortDir] = useState(-1);
  const [search, setSearch] = useState("");

  const { data: tickerData, isLoading } = useSWR(
    "market-tickers",
    () => api.tickers(TOP_PAIRS.join(",")),
    { refreshInterval: 15000, revalidateOnFocus: false }
  );

  const rows = Object.entries(tickerData ?? {}).map(([sym, d]) => ({
    symbol: sym,
    name: sym.replace("USDT",""),
    price: d.price,
    change: d.change_24h,
    volume: d.volume_24h,
    high: d.high_24h,
    low: d.low_24h,
  }));

  const filtered = rows
    .filter(r => r.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => sortDir * (a[sortKey] - b[sortKey]));

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => -d);
    else { setSortKey(key); setSortDir(-1); }
  };

  const SortTh = ({ k, children }) => (
    <th
      onClick={() => toggleSort(k)}
      className="py-2.5 px-3 text-left text-[10px] font-semibold text-tx-muted uppercase tracking-wider cursor-pointer select-none hover:text-tx transition-colors"
    >
      {children}
      {sortKey === k && <span className="ml-1">{sortDir < 0 ? "↓" : "↑"}</span>}
    </th>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 border-b border-border px-5 py-3 flex items-center gap-4">
        <h1 className="text-sm font-bold text-tx">Market Overview</h1>
        <div className="flex items-center gap-2 ml-auto">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Filter coins…"
            className="bg-bg border border-border rounded-lg px-3 py-1.5 text-xs text-tx placeholder-tx-muted outline-none focus:border-brand-blue transition-colors w-36"
          />
          <div className="flex items-center gap-1.5 text-[10px] text-tx-muted">
            <div className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse" />
            Live · 15s refresh
          </div>
          <EmailScheduleButton component="market" />
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {isLoading ? (
          <div className="flex items-center justify-center h-48 gap-2 text-tx-muted">
            <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Loading market data…</span>
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-bg-card border-b border-border z-10">
              <tr>
                <th className="py-2.5 pl-5 pr-3 text-left text-[10px] font-semibold text-tx-muted uppercase tracking-wider w-8">#</th>
                <th className="py-2.5 px-3 text-left text-[10px] font-semibold text-tx-muted uppercase tracking-wider">Asset</th>
                <SortTh k="price">Price</SortTh>
                <SortTh k="change">24h Change</SortTh>
                <SortTh k="volume">Volume</SortTh>
                <SortTh k="high">24h High</SortTh>
                <SortTh k="low">24h Low</SortTh>
                <th className="py-2.5 px-3 text-right text-[10px] font-semibold text-tx-muted uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr
                  key={r.symbol}
                  className="border-b border-border/40 hover:bg-border/10 transition-colors cursor-pointer"
                  onClick={() => onSelectSymbol?.(r.symbol)}
                >
                  <td className="py-3 pl-5 pr-3 text-tx-muted">{i + 1}</td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-blue/30 to-purple-600/30 flex items-center justify-center text-[10px] font-bold text-tx shrink-0">
                        {r.name.slice(0,2)}
                      </div>
                      <div>
                        <div className="font-bold text-tx">{r.name}</div>
                        <div className="text-[10px] text-tx-muted">/{r.symbol.includes("USDT") ? "USDT" : "BTC"}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-3 font-mono font-bold text-tx">
                    ${r.price?.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:r.price < 1 ? 6 : 2})}
                  </td>
                  <td className="py-3 px-3">
                    <Sparkbar change={r.change} />
                  </td>
                  <td className="py-3 px-3 font-mono text-tx-muted">
                    ${(r.volume / 1e6).toFixed(1)}M
                  </td>
                  <td className="py-3 px-3 font-mono text-brand-green">
                    ${r.high?.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}
                  </td>
                  <td className="py-3 px-3 font-mono text-brand-red">
                    ${r.low?.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button className="text-[10px] font-semibold text-brand-blue hover:text-blue-400 transition-colors px-2 py-1 rounded border border-brand-blue/20 hover:border-brand-blue/40">
                      Trade
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
