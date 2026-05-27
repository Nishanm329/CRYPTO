/**
 * Trading API wrapper for /api/trading/* endpoints
 */

import { api } from "./api";

export const tradingApi = {
  /**
   * Execute a trade based on a signal
   */
  executeTrade: async (symbol, direction, entryPrice, riskPct = 2.0, signalId = null) => {
    return api.request(`/api/trading/execute`, {
      method: "POST",
      body: JSON.stringify({
        symbol,
        direction,
        entry_price: entryPrice,
        risk_pct: riskPct,
        signal_id: signalId,
      }),
    });
  },

  /**
   * Get all open trades for the user
   */
  getOpenOrders: async (symbol = null) => {
    const params = new URLSearchParams();
    if (symbol) params.append("symbol", symbol);
    return api.request(`/api/trading/orders${params.toString() ? "?" + params : ""}`);
  },

  /**
   * Get closed trades and performance stats
   */
  getTradeHistory: async (symbol = null, limit = 50) => {
    const params = new URLSearchParams();
    if (symbol) params.append("symbol", symbol);
    params.append("limit", limit);
    return api.request(`/api/trading/history?${params}`);
  },

  /**
   * Close an open trade at market price or specified exit price
   */
  closeTrade: async (tradeId, exitPrice = null, exitReason = "MANUAL_EXIT") => {
    return api.request(`/api/trading/close`, {
      method: "POST",
      body: JSON.stringify({
        trade_id: tradeId,
        exit_price: exitPrice,
        exit_reason: exitReason,
      }),
    });
  },

  /**
   * Validate Binance API keys and store them securely
   * Server encrypts and stores keys, returns validation result
   */
  validateKeys: async (apiKey, apiSecret) => {
    return api.request(`/api/trading/validate-keys`, {
      method: "POST",
      body: JSON.stringify({
        api_key: apiKey,
        api_secret: apiSecret,
      }),
    });
  },

  /**
   * Store API keys securely on the backend
   * Keys are encrypted server-side
   */
  storeKeys: async (apiKey, apiSecret) => {
    return api.request(`/api/trading/keys/store`, {
      method: "POST",
      body: JSON.stringify({
        api_key: apiKey,
        api_secret: apiSecret,
      }),
    });
  },

  /**
   * Revoke stored API keys (disable trading)
   */
  revokeKeys: async () => {
    return api.request(`/api/trading/keys/revoke`, {
      method: "POST",
    });
  },

  /**
   * Check status of stored API keys
   * Returns validation status but NOT the actual keys
   */
  getKeysStatus: async () => {
    return api.request(`/api/trading/keys/status`);
  },
};

/**
 * Helper to format trade data for display
 */
export function formatTrade(trade) {
  return {
    ...trade,
    pnlColor: (trade.unrealized_pnl_pct || trade.realized_pnl_pct || 0) >= 0 ? "#22c55e" : "#ef4444",
    isWinning: (trade.unrealized_pnl_pct || trade.realized_pnl_pct || 0) >= 0,
  };
}

/**
 * Helper to calculate position size
 */
export function calculatePositionSize(walletBalance, riskPct, entryPrice) {
  const positionValue = walletBalance * (riskPct / 100);
  return positionValue / entryPrice;
}
