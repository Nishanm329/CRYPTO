import { useState, useEffect } from "react";
import clsx from "clsx";
import { tradingApi, calculatePositionSize } from "../lib/trading-api";
import { formatPrice } from "../lib/api";

export default function TradeExecutionModal({ signal, walletBalance = 10000, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [riskPct, setRiskPct] = useState(2);
  const [tradingMode, setTradingMode] = useState("PAPER");
  const [loadingSettings, setLoadingSettings] = useState(true);

  useEffect(() => {
    // Fetch trading settings to determine if PAPER or LIVE mode
    const fetchTradingSettings = async () => {
      try {
        const status = await tradingApi.getKeysStatus();
        if (status && status.trading_mode) {
          setTradingMode(status.trading_mode);
        }
      } catch (err) {
        console.warn("Failed to fetch trading mode, defaulting to PAPER:", err);
        setTradingMode("PAPER");
      } finally {
        setLoadingSettings(false);
      }
    };

    fetchTradingSettings();
  }, []);

  if (!signal) return null;

  const isLong = signal.direction === "LONG";
  const positionSize = calculatePositionSize(walletBalance, riskPct, signal.entry_price);
  const positionValue = positionSize * signal.entry_price;

  const handleExecute = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await tradingApi.executeTrade(
        signal.symbol,
        signal.direction,
        signal.entry_price,
        riskPct
      );

      if (result.error) {
        setError(result.error);
      } else {
        onSuccess && onSuccess(result);
        onClose();
      }
    } catch (err) {
      setError(err.message || "Failed to execute trade");
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
              <h2 className="text-lg font-bold text-tx">Execute Trade</h2>
              {tradingMode === "PAPER" && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                  [SIMULATED]
                </span>
              )}
              {tradingMode === "LIVE" && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-brand-red/20 text-brand-red">
                  [LIVE]
                </span>
              )}
            </div>
            <p className="text-xs text-tx-muted mt-1">Review and confirm trade details</p>
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
            <span className="text-sm font-bold text-tx">{signal.symbol}</span>
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

        {/* Risk & Position Size */}
        <div className="bg-bg rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-tx">Risk Per Trade</span>
            <span className="text-sm font-bold text-tx">{riskPct}%</span>
          </div>
          <input
            type="range"
            min="1"
            max="5"
            step="0.5"
            value={riskPct}
            onChange={(e) => setRiskPct(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-border rounded-lg appearance-none cursor-pointer"
            style={{
              background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${(riskPct / 5) * 100}%, #404040 ${(riskPct / 5) * 100}%, #404040 100%)`
            }}
          />
          <div className="text-xs text-tx-muted mt-2 text-center">
            {riskPct}% of ${walletBalance.toLocaleString()} = ${(positionValue).toFixed(2)}
          </div>
        </div>

        {/* Position Size Calculation */}
        <div className="border border-border rounded-lg p-4 mb-4 space-y-2">
          <div className="text-xs font-semibold text-tx mb-3">Position Calculation</div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-tx-muted">Wallet Balance</span>
            <span className="text-tx">${walletBalance.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-tx-muted">Risk Amount ({riskPct}%)</span>
            <span className="text-tx">${(walletBalance * (riskPct / 100)).toFixed(2)}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-tx-muted">Entry Price</span>
            <span className="text-tx">${formatPrice(signal.entry_price)}</span>
          </div>
          <div className="border-t border-border pt-2 flex items-center justify-between text-xs font-bold">
            <span className="text-tx-muted">Quantity to Buy</span>
            <span className="text-brand-blue">{positionSize.toFixed(8)} {signal.symbol.replace("USDT", "")}</span>
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
            disabled={loading || positionValue < 10}
            className={clsx(
              "flex-1 px-4 py-2.5 rounded-lg text-xs font-bold transition-all text-white",
              positionValue < 10
                ? "bg-gray-600 cursor-not-allowed opacity-50"
                : loading
                ? "bg-brand-blue/70"
                : "bg-brand-blue hover:bg-blue-500"
            )}
          >
            {loading ? "Executing..." : "Execute Trade"}
          </button>
        </div>

        {/* Warning */}
        <p className="text-[10px] text-tx-muted text-center mt-4">
          ⚠️ Trading involves risk. Start with small amounts. Do not risk capital you cannot afford to lose.
        </p>
      </div>
    </div>
  );
}
