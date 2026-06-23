import { useState, useEffect } from "react";
import clsx from "clsx";

const TIMEFRAMES = ["1m", "5m", "15m", "1H", "4H", "1D", "3D", "1W"];

function MoonIcon() {
  return (
    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function StarIcon() {
  return (
    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function IndicatorsIcon() {
  return (
    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

export default function Header({ symbol = "BTC/USDT", timeframe, onTimeframeChange }) {
  const [time, setTime] = useState(null);

  useEffect(() => {
    setTime(new Date());
    const iv = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);

  // Normalize display: "1h" → "1H", "3d" → "3D", "1w" → "1W" etc.
  const normalizeDisplay = (tf) => {
    if (!tf) return "1H";
    return tf.toUpperCase();
  };

  return (
    <header className="h-12 bg-bg-header border-b border-border flex items-center px-3 md:px-4 gap-2 md:gap-4 shrink-0 z-30 overflow-x-auto no-scrollbar">
      {/* Symbol selector */}
      <button className="flex items-center gap-2 bg-bg-card border border-border rounded-lg px-3 py-1.5 hover:border-border-light transition-colors shrink-0">
        <span className="text-sm font-bold text-tx">{symbol}</span>
        <ChevronIcon />
      </button>

      {/* Timeframe buttons */}
      <div className="flex items-center gap-0.5 bg-bg-card border border-border rounded-lg p-0.5 shrink-0">
        {TIMEFRAMES.map((tf) => {
          const isActive = normalizeDisplay(timeframe) === tf;
          return (
            <button
              key={tf}
              onClick={() => onTimeframeChange?.(tf.toLowerCase())}
              className={clsx(
                "px-3 py-1 text-xs font-semibold rounded-md transition-all",
                isActive
                  ? "bg-brand-blue text-white"
                  : "text-tx-muted hover:text-tx"
              )}
            >
              {tf}
            </button>
          );
        })}
      </div>

      {/* Divider */}
      <div className="h-5 w-px bg-border hidden md:block" />

      {/* Tool buttons */}
      <div className="hidden md:flex items-center gap-1">
        {[
          { icon: <IndicatorsIcon />, label: "Indicators" },
          { icon: <BellIcon />, label: "Alert" },
          { icon: <StarIcon />, label: "Watchlist" },
          { icon: <SettingsIcon />, label: "Settings" },
        ].map(({ icon, label }) => (
          <button
            key={label}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-tx-muted hover:text-tx hover:bg-border rounded-lg transition-colors text-xs"
          >
            {icon}
            <span className="hidden xl:block">{label}</span>
          </button>
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1 min-w-2" />

      {/* Right side */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Clock */}
        <span className="text-xs font-mono text-tx-muted hidden lg:block" suppressHydrationWarning>
          {time ? time.toUTCString().slice(17, 25) + " UTC" : ""}
        </span>

        {/* Theme toggle */}
        <button className="p-1.5 text-tx-muted hover:text-tx rounded-lg hover:bg-border transition-colors">
          <MoonIcon />
        </button>

        {/* Divider */}
        <div className="h-5 w-px bg-border" />

        {/* User */}
        <button className="flex items-center gap-2 px-2 py-1 hover:bg-border rounded-lg transition-colors">
          <div className="w-6 h-6 rounded-full bg-brand-blue/30 border border-brand-blue/50 flex items-center justify-center text-xs font-bold text-brand-blue">
            T
          </div>
          <span className="text-xs font-medium text-tx hidden sm:block">Trader</span>
          <ChevronIcon />
        </button>
      </div>
    </header>
  );
}
