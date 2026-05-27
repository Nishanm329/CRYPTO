import { useState, useEffect } from "react";
import { api, formatPrice, formatChange } from "../lib/api";
import clsx from "clsx";

const HEADER_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"];

export default function Navbar() {
  const [tickers, setTickers] = useState({});
  const [time, setTime] = useState(null);

  useEffect(() => {
    setTime(new Date());
    const iv = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const fetchTickers = async () => {
      try {
        const data = await api.tickers(HEADER_COINS.join(","));
        setTickers(data);
      } catch {}
    };
    fetchTickers();
    const iv = setInterval(fetchTickers, 15000);
    return () => clearInterval(iv);
  }, []);

  return (
    <nav className="sticky top-0 z-50 bg-surface/95 backdrop-blur border-b border-surface-2">
      <div className="max-w-screen-2xl mx-auto px-4 h-12 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
            AI
          </div>
          <span className="text-sm font-bold text-slate-200 hidden sm:block">
            CryptoSignal<span className="text-brand-blue">AI</span>
          </span>
        </div>

        {/* Ticker strip */}
        <div className="flex items-center gap-4 overflow-x-auto no-scrollbar">
          {HEADER_COINS.map((sym) => {
            const t = tickers[sym];
            const base = sym.replace("USDT", "");
            const up = t?.change_24h >= 0;
            return (
              <div key={sym} className="flex items-center gap-1.5 shrink-0">
                <span className="text-xs text-slate-500">{base}</span>
                <span className="text-xs font-mono text-slate-200">
                  ${t ? formatPrice(t.price) : "…"}
                </span>
                {t && (
                  <span className={clsx("text-xs", up ? "text-brand-green" : "text-brand-red")}>
                    {formatChange(t.change_24h)}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Right: clock + live indicator */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-1.5">
            <div className="live-dot" />
            <span className="text-xs text-slate-500 hidden sm:block">Live</span>
          </div>
          <span className="text-xs font-mono text-slate-500" suppressHydrationWarning>
            {time ? time.toUTCString().slice(17, 25) + " UTC" : ""}
          </span>
        </div>
      </div>
    </nav>
  );
}
