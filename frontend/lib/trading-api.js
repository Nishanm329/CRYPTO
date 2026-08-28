/**
 * Trading API wrapper for the Binance API-key connection flow in Settings
 * (/api/trading/keys/*).
 */

import { api } from "./api";

export const tradingApi = {
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
