import { useState } from "react";
import clsx from "clsx";

const TOOLTIPS = {
  confidence: "Model's certainty in the signal (0-100%)",
  sharpe: "Risk-adjusted return metric (higher = better)",
  pf: "Profit Factor: gross profit / gross loss",
  dd: "Maximum peak-to-trough decline",
  rr: "Risk-to-Reward ratio (TP:SL distance)",
  ema: "Exponential Moving Average - trend indicator",
  rsi: "Relative Strength Index - momentum indicator",
  macd: "Moving Average Convergence Divergence",
  bb: "Bollinger Bands - volatility indicator",
  vwap: "Volume Weighted Average Price",
  volume: "Trading volume bars",
  stoch: "Stochastic RSI - momentum oscillator",
  dominance: "Bitcoin's market cap as % of total crypto market",
  fear_greed: "Market sentiment from 0 (Fear) to 100 (Greed)",
};

export default function Tooltip({ term, children, position = "top" }) {
  const [show, setShow] = useState(false);
  const text = TOOLTIPS[term];

  if (!text) return children;

  return (
    <div className="relative inline-block">
      <div
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className="inline-flex items-center gap-1 cursor-help"
      >
        {children}
        <svg
          width="14"
          height="14"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="2"
          className="text-tx-muted"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h.01" />
        </svg>
      </div>

      {show && (
        <div
          className={clsx(
            "absolute z-50 bg-bg-card border border-border rounded-lg px-3 py-2 text-xs text-tx-muted",
            "whitespace-nowrap shadow-lg",
            position === "top" ? "bottom-full mb-2 left-1/2 -translate-x-1/2" : "top-full mt-2 left-1/2 -translate-x-1/2"
          )}
        >
          {text}
          <div
            className={clsx(
              "absolute w-0 h-0 border-4 border-transparent",
              position === "top"
                ? "top-full border-t-border border-t-4"
                : "bottom-full border-b-border border-b-4"
            )}
            style={{
              left: "50%",
              marginLeft: "-4px",
            }}
          />
        </div>
      )}
    </div>
  );
}
