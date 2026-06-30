import { useState, useCallback, useEffect, lazy, Suspense } from "react";
import { useRouter } from "next/router";
import dynamic from "next/dynamic";
import useSWR from "swr";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import StatsStrip from "../components/StatsStrip";
import TradingChart from "../components/TradingChart";
import RightPanel from "../components/RightPanel";
import SignalsView from "../components/SignalsView";
import Onboarding from "../components/Onboarding";
import ErrorBoundary from "../components/ErrorBoundary";
import { api, formatChange } from "../lib/api";
import clsx from "clsx";

// Lazy load heavy components
const ChartView = dynamic(() => import("../components/ChartView"), { ssr: false });
const MarketView = dynamic(() => import("../components/MarketView"), { ssr: false });
const NewsView = dynamic(() => import("../components/NewsView"), { ssr: false });
const AlertsView = dynamic(() => import("../components/AlertsView"), { ssr: false });
const PortfolioView = dynamic(() => import("../components/PortfolioView"), { ssr: false });
const SettingsView = dynamic(() => import("../components/SettingsView"), { ssr: false });
const StrategyLab = dynamic(() => import("../components/StrategyLab"), { ssr: false });
const BacktestView = dynamic(() => import("../components/BacktestView"), { ssr: false });
const TrackRecordView = dynamic(() => import("../components/TrackRecordView"), { ssr: false });
const BotView = dynamic(() => import("../components/BotView"), { ssr: false });
const DerivativesView = dynamic(() => import("../components/DerivativesView"), { ssr: false });
const WatchlistView = dynamic(() => import("../components/WatchlistView"), { ssr: false });
const LiquidationView = dynamic(() => import("../components/LiquidationView"), { ssr: false });

export default function Home() {
  const router = useRouter();
  const [timeframe, setTimeframe] = useState("1h");
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");
  const [activeNav, setActiveNav] = useState("dashboard");
  const [showOnboarding, setShowOnboarding] = useState(false);

  const { data: scanData, isLoading: scanLoading, mutate: mutateScan } = useSWR(
    `scan-${timeframe}`,
    () => api.scan(timeframe, 100, 50), // 100 pairs; reuses the backend's pre-warmed scan cache
    {
      // Poll fast while the backend is still computing a cold scan (warming flag).
      refreshInterval: (latest) => (latest?.warming ? 4000 : 60000),
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  const { data: signal, isLoading: signalLoading } = useSWR(
    selectedSymbol ? `signal-${selectedSymbol}-${timeframe}` : null,
    () => api.signal(selectedSymbol, timeframe),
    { refreshInterval: 30000, revalidateOnFocus: false, dedupingInterval: 30000 }
  );

  const { data: chartData, isLoading: chartLoading } = useSWR(
    selectedSymbol ? `chart-${selectedSymbol}-${timeframe}` : null,
    () => api.chart(selectedSymbol, timeframe, 100),
    { refreshInterval: 30000, revalidateOnFocus: false, dedupingInterval: 30000 }
  );

  // Lazy load sentiment (not critical for initial render)
  const { data: sentiment, isLoading: sentimentLoading } = useSWR(
    activeNav === "dashboard" ? "sentiment" : null,
    () => api.sentiment(),
    { refreshInterval: 300000, dedupingInterval: 300000 }
  );

  const { data: marketOverview, isLoading: overviewLoading } = useSWR(
    activeNav === "dashboard" ? "market-overview" : null,
    () => api.marketOverview(),
    { refreshInterval: 30000, revalidateOnFocus: false, dedupingInterval: 30000 }
  );

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.target instanceof Element && e.target.matches("input, textarea, select")) return;
      const key = e.key.toLowerCase();

      if (key === "c") setActiveNav("chart");
      else if (key === "s") setActiveNav("signals");
      else if (key === "p") setActiveNav("portfolio");
      else if (key === "a") setActiveNav("alerts");
      else if (key === "m") setActiveNav("market");
      else if (key === "n") setActiveNav("news");
      else if (key === "d") setActiveNav("dashboard");
      else if (key === "t") setActiveNav("backtest");
      else if (key === "r") setActiveNav("research");
      else if (key === "w") setActiveNav("watchlist");
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, []);

  // URL parameter support for symbol context
  useEffect(() => {
    if (router.isReady && router.query.symbol) {
      setSelectedSymbol(router.query.symbol);
    }
  }, [router.isReady, router.query.symbol]);

  const handleTimeframeChange = useCallback((tf) => {
    setTimeframe(tf);
    mutateScan();
  }, [mutateScan]);

  const handleSelectSymbol = useCallback((sym) => {
    setSelectedSymbol(sym);
    setActiveNav("dashboard"); // jump to dashboard when selecting a coin
  }, []);

  const displaySymbol = selectedSymbol ? selectedSymbol.replace("USDT", "/USDT") : "BTC/USDT";

  // ── Standalone views (no header/stats) ──────────────────────────────────────
  if (activeNav === "backtest") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <StrategyLab defaultSymbol={selectedSymbol} />
    </Layout>
  );

  if (activeNav === "chart") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <ChartView defaultSymbol={selectedSymbol} />
    </Layout>
  );

  if (activeNav === "signals") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <SignalsView onSelectSymbol={handleSelectSymbol} selectedSymbol={selectedSymbol} />
    </Layout>
  );

  if (activeNav === "scanner") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <SignalsView onSelectSymbol={handleSelectSymbol} selectedSymbol={selectedSymbol} variant="scanner" />
    </Layout>
  );

  if (activeNav === "market") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <MarketView onSelectSymbol={handleSelectSymbol} />
    </Layout>
  );

  if (activeNav === "news") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <NewsView />
    </Layout>
  );

  if (activeNav === "alerts") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <AlertsView />
    </Layout>
  );

  if (activeNav === "portfolio") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <PortfolioView />
    </Layout>
  );

  if (activeNav === "settings") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <SettingsView />
    </Layout>
  );

  if (activeNav === "track-record") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <TrackRecordView />
    </Layout>
  );

  if (activeNav === "bots") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <BotView defaultSymbol={selectedSymbol} />
    </Layout>
  );

  if (activeNav === "research") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <BacktestView />
    </Layout>
  );

  if (activeNav === "derivatives") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <DerivativesView defaultSymbol={selectedSymbol} />
    </Layout>
  );

  if (activeNav === "watchlist") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <WatchlistView onSelectSymbol={handleSelectSymbol} />
    </Layout>
  );

  if (activeNav === "liquidations") return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <LiquidationView defaultSymbol={selectedSymbol} />
    </Layout>
  );

  // ── Dashboard (default) ──────────────────────────────────────────────────────
  return (
    <Layout activeNav={activeNav} onNavChange={setActiveNav} showOnboarding={showOnboarding} onOnboardingComplete={() => setShowOnboarding(false)}>
      <Header
        symbol={displaySymbol}
        timeframe={timeframe}
        onTimeframeChange={handleTimeframeChange}
      />
      <StatsStrip marketOverview={marketOverview} sentiment={sentiment} />

      <div className="flex flex-col lg:flex-row flex-1 min-h-0 w-full overflow-y-auto lg:overflow-hidden">
        {/* Chart + bottom grid */}
        <div className="min-w-0 flex flex-col p-3 gap-3 lg:flex-1 lg:min-h-0 lg:pr-0 lg:overflow-hidden">
          <ErrorBoundary>
            <TradingChart chartData={chartData} loading={chartLoading} className="h-[360px] lg:h-auto lg:flex-1 lg:min-h-0" />
          </ErrorBoundary>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 shrink-0">
            {/* Top Signals */}
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-tx">Top Signals</span>
              </div>
              {scanLoading ? (
                <div className="flex items-center justify-center h-20">
                  <div className="w-4 h-4 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-tx-muted border-b border-border">
                        <th className="text-left pb-2 font-medium">Pair</th>
                        <th className="text-center pb-2 font-medium">TF</th>
                        <th className="text-center pb-2 font-medium">Signal</th>
                        <th className="text-right pb-2 font-medium">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(scanData?.signals ?? []).slice(0, 5).map((sig) => (
                        <tr
                          key={sig.symbol}
                          onClick={() => setSelectedSymbol(sig.symbol)}
                          className={clsx(
                            "border-b border-border/40 cursor-pointer hover:bg-border/30 transition-colors",
                            selectedSymbol === sig.symbol && "bg-brand-blue/5"
                          )}
                        >
                          <td className="py-2 font-semibold text-tx">
                            {sig.symbol.replace("USDT", "")}
                            <span className="text-tx-muted font-normal">/USDT</span>
                          </td>
                          <td className="py-2 text-center text-tx-muted">{sig.timeframe.toUpperCase()}</td>
                          <td className="py-2 text-center">
                            <span className={sig.direction === "LONG" ? "text-brand-green font-bold" : "text-brand-red font-bold"}>
                              {sig.direction === "LONG" ? "↑ BUY" : "↓ SELL"}
                            </span>
                          </td>
                          <td className="py-2 text-right font-bold font-mono" style={{
                            color: sig.confidence >= 75 ? "#00c896" : sig.confidence >= 55 ? "#f59e0b" : "#ef4444"
                          }}>
                            {sig.confidence}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <button
                    onClick={() => setActiveNav("signals")}
                    className="mt-3 text-xs text-brand-blue hover:text-blue-400 transition-colors"
                  >
                    View all signals →
                  </button>
                </>
              )}
            </div>

            {/* Market Overview */}
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-tx">Market Overview</span>
                <button onClick={() => setActiveNav("market")} className="text-[10px] text-brand-blue hover:text-blue-400 transition-colors">
                  Full table →
                </button>
              </div>
              {overviewLoading ? (
                <div className="flex items-center justify-center h-20">
                  <div className="w-4 h-4 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
                </div>
              ) : marketOverview ? (
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: "BTC/USDT", value: marketOverview.btc?.price?.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }), change: marketOverview.btc?.change_24h },
                    { label: "ETH/USDT", value: marketOverview.eth?.price?.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }), change: marketOverview.eth?.change_24h },
                    { label: "BTC.D", value: `${marketOverview.btc_dominance?.toFixed(2)}%`, change: marketOverview.btc_dominance_change },
                    { label: "TOTAL", value: `${marketOverview.total_mcap_trillions?.toFixed(2)}T`, change: marketOverview.total_mcap_change },
                    { label: "24h Volume", value: `$${((marketOverview.btc?.volume_24h ?? 0) + (marketOverview.eth?.volume_24h ?? 0)).toFixed(1)}B`, change: null },
                    { label: "Fear & Greed", value: `${sentiment?.fear_greed?.value ?? "—"}`, change: null },
                  ].map(({ label, value, change }) => (
                    <div key={label} className="bg-bg border border-border rounded-lg p-2.5">
                      <div className="text-[10px] text-tx-muted mb-1">{label}</div>
                      <div className={clsx("text-sm font-bold font-mono", change != null ? (change >= 0 ? "text-brand-green" : "text-brand-red") : "text-tx")}>
                        {value ?? "—"}
                      </div>
                      {change != null && (
                        <div className={clsx("text-[10px] font-medium mt-0.5", change >= 0 ? "text-brand-green" : "text-brand-red")}>
                          {change >= 0 ? "+" : ""}{change.toFixed(2)}%
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <RightPanel
          signal={signal}
          signalLoading={signalLoading && !!selectedSymbol}
          sentiment={sentiment}
          sentimentLoading={sentimentLoading}
        />
      </div>
    </Layout>
  );
}

// Shared layout shell (sidebar only)
function Layout({ activeNav, onNavChange, children, showOnboarding, onOnboardingComplete }) {
  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      <Sidebar activeNav={activeNav} onNavChange={onNavChange} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden pb-14 md:pb-0">
        {children}
      </div>
      {showOnboarding && <Onboarding onComplete={onOnboardingComplete} />}
    </div>
  );
}
