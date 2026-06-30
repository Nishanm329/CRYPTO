// All API calls go through the Next.js rewrite proxy (see next.config.js),
// so the browser only ever talks to its own origin — no CORS, no HTTPS
// mixed-content. The real backend URL is set via NEXT_PUBLIC_API_URL, which
// next.config.js uses as the rewrite destination (server-side).
const BASE = "";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "demo-key-public";
const requestCache = new Map();

// The backend runs on a free tier that sleeps after idle; a cold start can take
// ~30s+ to respond, so the request timeout must be generous and we retry once on
// network/timeout failures before surfacing an error to the user.
const REQUEST_TIMEOUT_MS = 45000;

async function fetchWithTimeout(url, options) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function doFetch(path, opts) {
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${API_KEY}`,
    ...opts.headers,
  };

  const startTime = performance.now();
  let res;
  try {
    res = await fetchWithTimeout(`${BASE}${path}`, { headers, ...opts });
  } catch (e) {
    // AbortError (timeout) or network failure — likely a cold/waking backend.
    throw new Error("Server is waking up — please retry in a moment.");
  }

  if (path.includes("/api/chart/")) {
    console.log(`[API] Chart request: ${(performance.now() - startTime).toFixed(1)}ms`);
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 429) {
      console.error("Rate limit exceeded:", err);
      throw new Error("Daily quota exceeded. Please try again tomorrow.");
    }
    if (res.status === 401) {
      console.error("Authentication failed:", err);
      throw new Error("Invalid or missing API key");
    }
    // 502/503/504 from the proxy means the backend is still spinning up.
    if (res.status === 502 || res.status === 503 || res.status === 504) {
      throw new Error("Server is waking up — please retry in a moment.");
    }
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

async function apiFetch(path, opts = {}) {
  // Determine cache duration based on endpoint type
  let cacheDuration = 5000; // Default 5s
  if (path.includes('/api/sentiment')) cacheDuration = 300000; // 5m for sentiment
  else if (path.includes('/api/market-overview')) cacheDuration = 120000; // 2m for market data
  else if (path.includes('/api/chart/')) cacheDuration = 30000; // 30s for charts

  const isGet = !opts.method || opts.method === "GET";
  const cacheKey = `GET:${path}`;
  // Cache GET requests to deduplicate rapid in-flight requests
  if (isGet && requestCache.has(cacheKey)) {
    return requestCache.get(cacheKey);
  }

  // Retry once on a cold-start failure (network/timeout/5xx) before giving up.
  const attempt = async (retriesLeft) => {
    try {
      return await doFetch(path, opts);
    } catch (e) {
      if (retriesLeft > 0 && /waking up/.test(e.message)) {
        return attempt(retriesLeft - 1);
      }
      throw e;
    }
  };

  const promise = attempt(1);

  if (isGet) {
    requestCache.set(cacheKey, promise);
    setTimeout(() => requestCache.delete(cacheKey), cacheDuration);
    // Never let a rejected promise stay cached — it would poison retries.
    promise.catch(() => requestCache.delete(cacheKey));
  }

  return promise;
}

export const api = {
  request: (path, opts) => apiFetch(path, opts),

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

  derivatives: (symbol) => apiFetch(`/api/derivatives/${symbol}`),

  liquidations: (symbol) => apiFetch(`/api/liquidations/${symbol}`),

  trackRecord: () => apiFetch("/api/track-record"),

  bots: () => apiFetch("/api/bots"),

  createBot: (mode, symbol, timeframe, config) =>
    apiFetch("/api/bots", { method: "POST", body: JSON.stringify({ mode, symbol, timeframe, config }) }),

  stopBot: (id) => apiFetch(`/api/bots/${id}/stop`, { method: "POST" }),

  startBot: (id) => apiFetch(`/api/bots/${id}/start`, { method: "POST" }),

  deleteBot: (id) => apiFetch(`/api/bots/${id}`, { method: "DELETE" }),

  combinationBacktest: (symbol, timeframe = "1d", years = 6) =>
    apiFetch(
      `/api/backtest/combinations/${symbol}?timeframe=${timeframe}&years=${years}`
    ),

  walkForwardBacktest: (symbol, timeframe = "1d", years = 6, nSplits = 5) =>
    apiFetch(
      `/api/backtest/walk-forward/${symbol}?timeframe=${timeframe}&years=${years}&n_splits=${nSplits}`
    ),
};

export function formatPrice(price, symbol = "") {
  if (price == null || isNaN(price)) return "–";
  const abs = Math.abs(price);
  // Scale precision by magnitude so large prices stay clean (BTC → 2dp)
  // while micro-caps keep meaningful digits.
  let precision;
  if (abs >= 1000) precision = 2;
  else if (abs >= 1) precision = 3;
  else if (abs >= 0.1) precision = 4;
  else if (abs >= 0.001) precision = 6;
  else precision = 8;
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
