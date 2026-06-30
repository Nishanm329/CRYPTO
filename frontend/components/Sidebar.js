import { useState } from "react";
import clsx from "clsx";

const NAV_MAIN = [
  {
    key: "dashboard", label: "Dashboard",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    key: "watchlist", label: "Watchlist",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    ),
  },
  {
    key: "chart", label: "Chart",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    key: "signals", label: "Signals",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
  {
    key: "scanner", label: "Scanner",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
  },
  {
    key: "market", label: "Market",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
  },
  {
    key: "derivatives", label: "Derivatives", futures: true,
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="m12 2 9 5-9 5-9-5 9-5Z" />
        <path d="m3 12 9 5 9-5" />
        <path d="m3 17 9 5 9-5" />
      </svg>
    ),
  },
  {
    key: "liquidations", label: "Liquidations", futures: true,
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5Z" />
      </svg>
    ),
  },
  {
    key: "news", label: "News",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" />
        <path d="M18 14h-8M15 18h-5M10 6h8v4h-8V6Z" />
      </svg>
    ),
  },
  {
    key: "alerts", label: "Alerts",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    ),
  },
  {
    key: "backtest", label: "Backtest",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
  },
  {
    key: "track-record", label: "Track Record",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M3 3v18h18" />
        <path d="M7 14l4-4 3 3 5-6" />
      </svg>
    ),
  },
  {
    key: "bots", label: "Bots",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="11" width="18" height="10" rx="2" />
        <circle cx="8" cy="16" r="1" />
        <circle cx="16" cy="16" r="1" />
        <path d="M12 7v4M12 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />
      </svg>
    ),
  },
  {
    key: "research", label: "Research",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
        <path d="M21 3v5h-5" />
        <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
        <path d="M3 21v-5h5" />
      </svg>
    ),
  },
  {
    key: "portfolio", label: "Portfolio",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <rect x="2" y="7" width="20" height="14" rx="2" />
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
      </svg>
    ),
  },
  {
    key: "settings", label: "Settings",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
];

// Derivatives & Liquidations rely on Binance USDⓈ-M futures data, which is
// geoblocked from the production backend's region. Hide them in prod builds;
// they stay available in local dev where the futures API is reachable.
const HIDE_FUTURES = process.env.NODE_ENV === "production";
const NAV_VISIBLE = NAV_MAIN.filter((n) => !(HIDE_FUTURES && n.futures));

const NAV_BOTTOM = [
  {
    key: "help", label: "Help",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01" />
      </svg>
    ),
  },
  {
    key: "logout", label: "Logout",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
      </svg>
    ),
  },
];

export default function Sidebar({ activeNav = "dashboard", onNavChange }) {
  return (
    <>
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-[160px] shrink-0 bg-bg-sidebar border-r border-border flex-col h-full overflow-hidden">
        {/* Logo */}
        <div className="px-4 py-4 flex items-center gap-2 border-b border-border">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-blue to-purple-600 flex items-center justify-center shrink-0">
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth="2.5">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" fill="white" stroke="none" />
            </svg>
          </div>
          <span className="text-sm font-bold text-tx leading-tight">
            Crypto<span className="text-brand-blue">Expert</span>
          </span>
        </div>

        {/* Main nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto no-scrollbar">
          {NAV_VISIBLE.map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => onNavChange?.(key)}
              className={clsx(
                "nav-item w-full",
                activeNav === key && "nav-item-active"
              )}
              title={label}
            >
              <span className={clsx(activeNav === key ? "text-brand-blue" : "text-tx-muted")}>
                {icon}
              </span>
              <span className="text-xs font-medium">{label}</span>
            </button>
          ))}
        </nav>

        {/* Upgrade to Pro */}
        <div className="px-2 pb-2">
          <button className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg bg-brand-gold/10 border border-brand-gold/20 hover:bg-brand-gold/15 transition-colors">
            <svg width="16" height="16" fill="#f4b942" viewBox="0 0 24 24">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            <span className="text-xs font-semibold text-brand-gold">Upgrade to Pro</span>
          </button>
        </div>

        {/* Bottom nav */}
        <div className="px-2 pb-3 border-t border-border pt-2 space-y-0.5">
          {NAV_BOTTOM.map(({ key, label, icon }) => (
            <button key={key} className="nav-item w-full" title={label}>
              <span className="text-tx-muted">{icon}</span>
              <span className="text-xs font-medium">{label}</span>
            </button>
          ))}
        </div>
      </aside>

      {/* Mobile - Bottom tab bar + More sheet */}
      <MobileNav activeNav={activeNav} onNavChange={onNavChange} />
    </>
  );
}

// Keys shown directly in the mobile bottom tab bar (rest go in the "More" sheet)
const BOTTOM_TAB_KEYS = ["dashboard", "chart", "signals", "scanner"];

function MoreIcon() {
  return (
    <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <circle cx="5" cy="12" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="19" cy="12" r="1.6" />
    </svg>
  );
}

function MobileNav({ activeNav, onNavChange }) {
  const [moreOpen, setMoreOpen] = useState(false);
  const primary = BOTTOM_TAB_KEYS.map((k) => NAV_VISIBLE.find((n) => n.key === k)).filter(Boolean);
  const moreItems = NAV_VISIBLE.filter((n) => !BOTTOM_TAB_KEYS.includes(n.key));
  const moreActive = moreItems.some((n) => n.key === activeNav);

  const select = (key) => {
    onNavChange?.(key);
    setMoreOpen(false);
  };

  return (
    <>
      {/* Bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 h-14 bg-bg-sidebar/95 backdrop-blur border-t border-border flex items-stretch px-1 pb-[env(safe-area-inset-bottom)]">
        {primary.map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => select(key)}
            className={clsx(
              "flex-1 flex flex-col items-center justify-center gap-0.5 rounded-lg transition-colors [&_svg]:w-[19px] [&_svg]:h-[19px]",
              activeNav === key ? "text-brand-blue" : "text-tx-muted"
            )}
          >
            {icon}
            <span className="text-[10px] font-medium leading-none">{label}</span>
          </button>
        ))}
        <button
          onClick={() => setMoreOpen(true)}
          className={clsx(
            "flex-1 flex flex-col items-center justify-center gap-0.5 rounded-lg transition-colors",
            moreActive ? "text-brand-blue" : "text-tx-muted"
          )}
        >
          <MoreIcon />
          <span className="text-[10px] font-medium leading-none">More</span>
        </button>
      </nav>

      {/* More sheet */}
      {moreOpen && (
        <div className="md:hidden fixed inset-0 z-50" onClick={() => setMoreOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="absolute bottom-0 inset-x-0 bg-bg-sidebar border-t border-border rounded-t-2xl p-4 pb-[calc(1.25rem+env(safe-area-inset-bottom))]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-10 h-1 rounded-full bg-border mx-auto mb-4" />
            <div className="grid grid-cols-4 gap-2">
              {moreItems.map(({ key, label, icon }) => (
                <button
                  key={key}
                  onClick={() => select(key)}
                  className={clsx(
                    "flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl transition-colors [&_svg]:w-[20px] [&_svg]:h-[20px]",
                    activeNav === key ? "bg-brand-blue/15 text-brand-blue" : "text-tx-muted hover:bg-border/40"
                  )}
                >
                  {icon}
                  <span className="text-[10px] font-medium text-center leading-tight">{label}</span>
                </button>
              ))}
              {NAV_BOTTOM.map(({ key, label, icon }) => (
                <button
                  key={key}
                  className="flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl text-tx-muted hover:bg-border/40 transition-colors [&_svg]:w-[20px] [&_svg]:h-[20px]"
                >
                  {icon}
                  <span className="text-[10px] font-medium text-center leading-tight">{label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
