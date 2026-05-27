/**
 * Secure storage utilities for sensitive data (API keys, secrets, etc.)
 *
 * SECURITY NOTE: localStorage is NOT truly secure for sensitive data.
 * For production, API keys should be:
 * 1. Encrypted by the server (done: see backend/crypto_utils.py)
 * 2. Never stored in browser localStorage
 * 3. Transmitted only over HTTPS
 * 4. Stored server-side in encrypted form
 *
 * MVP uses server-side encryption. Secure browser storage coming in Phase C.2
 */

const STORAGE_KEY_PREFIX = "trading_";
const SECURE_KEYS = ["binance_api_key", "binance_api_secret"];

/**
 * Store a sensitive value securely.
 * In MVP: Uses localStorage with warning
 * In production: Would use browser's StorageAPI with encryption
 */
export function secureStore(key, value) {
  if (!SECURE_KEYS.includes(key)) {
    console.warn(`⚠️ Key "${key}" is not recognized as secure`);
  }

  try {
    // In production, this would encrypt before storing
    // For now, store with a prefix and warning
    const storageKey = `${STORAGE_KEY_PREFIX}${key}`;
    localStorage.setItem(storageKey, value);

    console.warn(`⚠️ SECURITY: "${key}" stored in localStorage. Use secure backend storage in production.`);
    return true;
  } catch (err) {
    console.error(`Failed to store ${key}:`, err);
    return false;
  }
}

/**
 * Retrieve a sensitive value.
 */
export function secureRetrieve(key) {
  try {
    const storageKey = `${STORAGE_KEY_PREFIX}${key}`;
    return localStorage.getItem(storageKey);
  } catch (err) {
    console.error(`Failed to retrieve ${key}:`, err);
    return null;
  }
}

/**
 * Delete a sensitive value.
 */
export function secureDelete(key) {
  try {
    const storageKey = `${STORAGE_KEY_PREFIX}${key}`;
    localStorage.removeItem(storageKey);
    return true;
  } catch (err) {
    console.error(`Failed to delete ${key}:`, err);
    return false;
  }
}

/**
 * Check if a sensitive key exists.
 */
export function secureHasKey(key) {
  try {
    const storageKey = `${STORAGE_KEY_PREFIX}${key}`;
    return localStorage.getItem(storageKey) !== null;
  } catch (err) {
    return false;
  }
}

/**
 * Clear all stored sensitive data.
 * WARNING: This removes ALL trading credentials.
 */
export function secureClearAll() {
  try {
    const keys = Object.keys(localStorage);
    keys.forEach((key) => {
      if (key.startsWith(STORAGE_KEY_PREFIX)) {
        localStorage.removeItem(key);
      }
    });
    return true;
  } catch (err) {
    console.error("Failed to clear sensitive data:", err);
    return false;
  }
}

/**
 * Validate API key format (basic check)
 */
export function validateApiKey(key) {
  if (!key || typeof key !== "string") return false;
  // Binance API keys are typically 64 characters
  return key.length > 20 && key.length < 200;
}

/**
 * Validate API secret format (basic check)
 */
export function validateApiSecret(secret) {
  if (!secret || typeof secret !== "string") return false;
  // Binance API secrets are typically 64 characters
  return secret.length > 20 && secret.length < 200;
}
