const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "demo-key-public";
const requestCache = new Map();

async function apiFetch(path, opts = {}) {
  // Determine cache duration based on endpoint type
  let cacheDuration = 5000; // Default 5s
  if (path.includes('/api/sentiment')) cacheDuration = 300000; // 5m for sentiment
  else if (path.includes('/api/market-overview')) cacheDuration = 120000; // 2m for market data
  else if (path.includes('/api/chart/')) cacheDuration = 30000; // 30s for charts

  // Cache GET requests to deduplicate rapid requests
  const cacheKey = `GET:${path}`;
  if (!opts.method || opts.method === "GET") {
    if (requestCache.has(cacheKey)) {
      return requestCache.get(cacheKey);
    }
  }

  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${API_KEY}`,
    ...opts.headers,
  };

  const startTime = performance.now();
  const promise = fetch(`${BASE}${path}`, {
    headers,
    ...opts,
  }).then(async (res) => {
    const elapsed = performance.now() - startTime;
    const isChartCall = path.includes('/api/chart/');
    if (isChartCall) {
      console.log(`[API] Chart request: ${elapsed.toFixed(1)}ms`);
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));

      // Handle quota exceeded error
      if (res.status === 429) {
        console.error("Rate limit exceeded:", err);
        throw new Error("Daily quota exceeded. Please try again tomorrow.");
      }

      // Handle authentication errors
      if (res.status === 401) {
        console.error("Authentication failed:", err);
        throw new Error("Invalid or missing API key");
      }

      throw new Error(err.detail || `API error: ${res.status}`);
    }
    return res.json();
  });

  // Cache the promise for GET requests
  if (!opts.method || opts.method === "GET") {
    requestCache.set(cacheKey, promise);
    setTimeout(() => requestCache.delete(cacheKey), cacheDuration);
  }

  return promise;
}

export const api = {
  scan: (timeframe = "1h", maxPairs = 50, minConfidence = 50) =>
    apiFetch(`/api/scan?timeframe=${timeframe}&max_pairs=${maxPairs}&min_confidence=${minConfidence}`),

  signal: (symbol, timeframe = "1h") =>
    apiFetch(`/api/signal/${symbol}?timeframe=${timeframe}`),

  chart: (symbol, timeframe = "1h", limit = 200) =>
    apiFetch(`/api/chart/${symbol}?timeframe=${timeframe}&limit=${limit}`),

  sentiment: () => apiFetch("/api/sentiment"),

  backtest: (symbol, timeframe = "1h", limit = 500) =>
    apiFetch(`/api/backtest/${symbol}?timeframe=${timeframe}&limit=${limit}`),

  tickers: (symbols) =>
    apiFetch(`/api/tickers${symbols ? `?symbols=${symbols}` : ""}`),

  pairs: () => apiFetch("/api/pairs"),

  marketOverview: () => apiFetch("/api/market-overview"),

  combinationBacktest: (symbol, timeframe = "1d", years = 6) =>
    apiFetch(
      `/api/backtest/combinations/${symbol}?timeframe=${timeframe}&years=${years}`
    ),
};

export function formatPrice(price, symbol = "") {
  if (!price) return "–";
  const numStr = price.toString();
  const decimals = numStr.includes(".") ? numStr.split(".")[1].replace(/0+$/, "").length : 0;
  const precision = Math.max(2, Math.min(decimals, 8));
  return price.toLocaleString("en-US", {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
}

export function formatVolume(vol) {
  if (vol >= 1e9) return `$${(vol / 1e9).toFixed(1)}B`;
  if (vol >= 1e6) return `$${(vol / 1e6).toFixed(1)}M`;
  if (vol >= 1e3) return `$${(vol / 1e3).toFixed(1)}K`;
  return `$${vol.toFixed(0)}`;
}

export function formatChange(pct) {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export function confidenceColor(conf) {
  if (conf >= 75) return "#22c55e";
  if (conf >= 55) return "#f59e0b";
  return "#ef4444";
}

export function confidenceLabel(conf) {
  if (conf >= 75) return "Strong";
  if (conf >= 60) return "Moderate";
  if (conf >= 45) return "Weak";
  return "Low";
}
