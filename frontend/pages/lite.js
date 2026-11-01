import { useState } from "react";
import Head from "next/head";
import clsx from "clsx";
import SignalsView from "../components/SignalsView";
import ErrorBoundary from "../components/ErrorBoundary";

const TABS = [
  ["signals", "Signals"],
  ["scanner", "Scanner"],
];

// Stripped-down app: just Signals and Scanner. The full app lives at "/".
export default function Lite() {
  const [tab, setTab] = useState("signals");
  const [selected, setSelected] = useState(null);

  // No chart here — picking a coin opens it in the full app.
  const openChart = (sym) => {
    setSelected(sym);
    window.location.href = `/?symbol=${encodeURIComponent(sym)}`;
  };

  return (
    <div className="h-screen flex flex-col bg-bg text-tx">
      <Head><title>CryptoExpert Lite</title></Head>
      <nav className="shrink-0 flex items-center gap-1 px-4 h-12 border-b border-border">
        <span className="text-sm font-bold mr-4">Crypto<span className="text-brand-blue">Expert</span></span>
        {TABS.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={clsx("px-4 py-1.5 rounded-lg text-sm font-semibold transition-all",
              tab === key ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx")}
          >{label}</button>
        ))}
        <a href="/" className="ml-auto text-[11px] text-tx-muted hover:text-tx underline underline-offset-2">Full app</a>
      </nav>
      <div className="flex-1 min-h-0">
        <ErrorBoundary>
          <SignalsView key={tab} variant={tab} lite onSelectSymbol={openChart} selectedSymbol={selected} />
        </ErrorBoundary>
      </div>
    </div>
  );
}
