import { useState } from "react";
import clsx from "clsx";
import { api, formatPrice } from "../lib/api";

// Same denominations as the Track Record's "$ risked per trade" selector, so
// the two features present the identical concept the same way.
const POSITION_SIZES = [50, 100, 250, 500, 1000];

export default function TradeExecutionModal({ signal, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [positionUsd, setPositionUsd] = useState(100);

  if (!signal) return null;

  const isLong = signal.direction === "LONG";

  const handleExecute = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.createBot("signal", signal.symbol, signal.timeframe, {
        position_usd: positionUsd,
        // Floor set to this signal's own confidence so the bot is guaranteed to
        // pick it up on seed (bots replay recent history immediately on
        // creation), then keeps trading any future setup at least this good.
        min_confidence: signal.confidence,
        sizing_mode: "risk",
      });
      onSuccess && onSuccess(result);
      onClose();
    } catch (err) {
      setError(err.message || "Failed to start bot");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-bg-card border border-border rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-tx">Start Paper Bot</h2>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                PAPER
              </span>
            </div>
            <p className="text-xs text-tx-muted mt-1">
              Simulated against real price action — no API keys, no live orders
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-tx-muted hover:text-tx text-2xl leading-none"
          >
            ✕
          </button>
        </div>

        {/* Signal Details */}
        <div className="bg-bg rounded-lg p-4 mb-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-tx-muted">Symbol</span>
            <span className="text-sm font-bold text-tx">
              {signal.symbol.replace("USDT", "")}<span className="text-tx-muted font-normal">/USDT</span>
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-tx-muted">Direction</span>
            <span className={clsx(
              "text-sm font-bold px-2 py-1 rounded",
              isLong
                ? "bg-brand-green/20 text-brand-green"
                : "bg-brand-red/20 text-brand-red"
            )}>
              {isLong ? "▲ LONG" : "▼ SHORT"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-tx-muted">Entry Price</span>
            <span className="text-sm font-mono text-tx">${formatPrice(signal.entry_price)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-tx-muted">Confidence</span>
            <span className="text-sm font-bold text-tx" style={{ color: signal.confidence >= 75 ? "#22c55e" : signal.confidence >= 55 ? "#f59e0b" : "#ef4444" }}>
              {signal.confidence}%
            </span>
          </div>
        </div>

        {/* Position Size */}
        <div className="bg-bg rounded-lg p-4 mb-4">
          <div className="text-xs font-semibold text-tx mb-3">Risked $ per trade (1R)</div>
          <div className="flex items-center flex-wrap gap-2">
            {POSITION_SIZES.map((v) => (
              <button
                key={v}
                onClick={() => setPositionUsd(v)}
                className={clsx(
                  "text-xs px-2.5 py-1.5 rounded-lg border transition-colors font-semibold",
                  positionUsd === v
                    ? "bg-brand-blue/15 border-brand-blue text-brand-blue"
                    : "border-border text-tx-muted hover:text-tx"
                )}
              >
                ${v}
              </button>
            ))}
          </div>
          <div className="text-xs text-tx-muted mt-3 text-center">
            A stop-out on this bot loses exactly ${positionUsd}, regardless of stop distance
          </div>
        </div>

        {/* Take Profits */}
        {signal.take_profits && signal.take_profits.length > 0 && (
          <div className="bg-bg rounded-lg p-4 mb-4">
            <div className="text-xs font-semibold text-tx mb-2">Take Profit Levels</div>
            <div className="space-y-1.5">
              {signal.take_profits.map((tp, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-tx-muted">TP{tp.level}</span>
                  <span className="text-tx font-mono">${formatPrice(tp.price)} (+{tp.pct_gain.toFixed(1)}%)</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stop Loss */}
        {signal.stop_loss && (
          <div className="bg-bg rounded-lg p-4 mb-4">
            <div className="flex items-center justify-between text-xs">
              <span className="text-tx-muted">Stop Loss</span>
              <span className="text-brand-red font-mono">${formatPrice(signal.stop_loss)}</span>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="bg-brand-red/20 border border-brand-red/40 rounded-lg p-3 mb-4 text-xs text-brand-red">
            {error}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 px-4 py-2.5 rounded-lg border border-border text-xs font-semibold text-tx hover:border-border-light transition-all disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleExecute}
            disabled={loading}
            className={clsx(
              "flex-1 px-4 py-2.5 rounded-lg text-xs font-bold transition-all text-white",
              loading ? "bg-brand-blue/70" : "bg-brand-blue hover:bg-blue-500"
            )}
          >
            {loading ? "Starting…" : "Start Paper Bot"}
          </button>
        </div>

        {/* Info */}
        <p className="text-[10px] text-tx-muted text-center mt-4">
          This creates a paper-trading bot in the Bots tab that trades this setup and any future signal on {signal.symbol.replace("USDT", "")}/USDT at or above {signal.confidence}% confidence.
        </p>
      </div>
    </div>
  );
}
