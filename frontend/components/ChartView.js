import { useState, useEffect, useMemo } from "react";
import useSWR from "swr";
import TradingChart from "./TradingChart";
import { api } from "../lib/api";
import clsx from "clsx";

const TFS = ["1m","5m","15m","1h","4h","1d","3d","1w"];
const POPULAR = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT"];
const SPEEDS = [0.5, 1, 2, 4];

// Truncate every time-series in chartData to the first `count` bars so the
// chart reveals history progressively (bar replay). Indicators/markers are
// aligned to bars by time, so we filter them to the set of revealed bar times —
// robust whether `time` is a unix number or a business-day object.
function sliceChart(data, count) {
  if (!data?.bars?.length) return data;
  const n = Math.max(1, Math.min(count, data.bars.length));
  const bars = data.bars.slice(0, n);
  const allowed = new Set(bars.map((b) => JSON.stringify(b.time)));
  const cut = (arr) => (Array.isArray(arr) ? arr.filter((p) => allowed.has(JSON.stringify(p.time))) : []);
  const lastVal = (arr) => (arr.length ? arr[arr.length - 1].value : undefined);

  const ema7 = cut(data.ema7), ema25 = cut(data.ema25);
  const bb_upper = cut(data.bb_upper), bb_middle = cut(data.bb_middle), bb_lower = cut(data.bb_lower);
  const vwap = cut(data.vwap), rsi = cut(data.rsi);
  const macd = cut(data.macd), macd_hist = cut(data.macd_hist), macd_signal = cut(data.macd_signal);
  const stoch_k = cut(data.stoch_k), stoch_d = cut(data.stoch_d);

  return {
    ...data,
    bars,
    volume: data.volume ? cut(data.volume) : undefined,
    ema7, ema25, bb_upper, bb_middle, bb_lower, vwap,
    elliott_wave: cut(data.elliott_wave),
    elliott_wave_markers: cut(data.elliott_wave_markers),
    signals: cut(data.signals),
    rsi, macd, macd_hist, macd_signal, stoch_k, stoch_d,
    latest_values: {
      ema7: lastVal(ema7), ema25: lastVal(ema25),
      bb_upper: lastVal(bb_upper), bb_middle: lastVal(bb_middle), bb_lower: lastVal(bb_lower),
      vwap: lastVal(vwap), rsi: lastVal(rsi),
      macd: lastVal(macd), macd_signal: lastVal(macd_signal), macd_hist: lastVal(macd_hist),
      stoch_k: lastVal(stoch_k), stoch_d: lastVal(stoch_d),
    },
  };
}

export default function ChartView({ defaultSymbol = "BTCUSDT" }) {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [timeframe, setTimeframe] = useState("1d");
  const [query, setQuery] = useState("");
  const [replay, setReplay] = useState(false);
  const [replayIdx, setReplayIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  const { data: pairs } = useSWR("pairs", api.pairs, { revalidateOnFocus: false });
  const { data: chartData, isLoading } = useSWR(
    `chart-${symbol}-${timeframe}`,
    () => api.chart(symbol, timeframe, 300),
    { refreshInterval: replay ? 0 : 30000, revalidateOnFocus: false }
  );

  const totalBars = chartData?.bars?.length ?? 0;

  // Leaving a symbol/timeframe exits replay (data shape changes underneath).
  useEffect(() => {
    setReplay(false);
    setPlaying(false);
    setReplayIdx(0);
  }, [symbol, timeframe]);

  // Initialise / clamp the replay cursor against the loaded data.
  useEffect(() => {
    if (!replay || !totalBars) return;
    setReplayIdx((i) => (i >= 1 && i <= totalBars ? i : Math.max(1, Math.floor(totalBars * 0.4))));
  }, [replay, totalBars]);

  // Playback ticker — reveal one bar per interval, scaled by speed.
  useEffect(() => {
    if (!replay || !playing || !totalBars) return;
    const id = setInterval(() => setReplayIdx((i) => Math.min(totalBars, i + 1)), 700 / speed);
    return () => clearInterval(id);
  }, [replay, playing, speed, totalBars]);

  // Auto-pause when the cursor reaches the end.
  useEffect(() => {
    if (replay && playing && totalBars && replayIdx >= totalBars) setPlaying(false);
  }, [replay, playing, replayIdx, totalBars]);

  const displayData = useMemo(
    () => (replay && chartData ? sliceChart(chartData, replayIdx) : chartData),
    [replay, chartData, replayIdx]
  );

  const stepBack = () => { setPlaying(false); setReplayIdx((i) => Math.max(1, i - 1)); };
  const stepFwd = () => { setPlaying(false); setReplayIdx((i) => Math.min(totalBars, i + 1)); };

  const allPairs = pairs?.pairs ?? POPULAR;
  const filtered = query
    ? allPairs.filter(p => p.toLowerCase().includes(query.toLowerCase())).slice(0, 20)
    : POPULAR;

  return (
    <div className="flex flex-col lg:flex-row h-full overflow-hidden">
      {/* Left: symbol list (top strip on mobile) */}
      <div className="w-full lg:w-44 shrink-0 border-b lg:border-b-0 lg:border-r border-border flex flex-col bg-bg-sidebar">
        <div className="p-2">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search pair…"
            className="w-full bg-bg border border-border rounded-lg px-2.5 py-1.5 text-xs text-tx placeholder-tx-muted outline-none focus:border-brand-blue transition-colors"
          />
        </div>
        <div className="lg:flex-1 flex lg:flex-col overflow-x-auto lg:overflow-y-auto no-scrollbar px-1 pb-2 gap-1 lg:gap-0">
          {filtered.map(p => (
            <button
              key={p}
              onClick={() => setSymbol(p)}
              className={clsx(
                "shrink-0 lg:w-full text-left px-2.5 py-2 rounded-lg text-xs font-semibold transition-all lg:mb-0.5 whitespace-nowrap",
                symbol === p ? "bg-brand-blue/15 text-brand-blue" : "text-tx-muted hover:text-tx hover:bg-border/30"
              )}
            >
              {p.replace("USDT","")}<span className="text-tx-dim font-normal">/USDT</span>
            </button>
          ))}
        </div>
      </div>

      {/* Right: chart */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* TF bar */}
        <div className="h-10 shrink-0 border-b border-border flex items-center px-3 lg:px-4 gap-3 lg:gap-4 overflow-x-auto no-scrollbar">
          <span className="text-sm font-bold text-tx shrink-0">{symbol.replace("USDT","")}<span className="text-tx-muted font-normal">/USDT</span></span>
          <div className="flex gap-0.5 shrink-0">
            {TFS.map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={clsx(
                  "px-2.5 py-1 rounded text-xs font-semibold transition-all",
                  timeframe === tf ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
                )}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>

          <button
            onClick={() => setReplay((r) => !r)}
            title="Bar replay — step through history candle by candle"
            className={clsx(
              "ml-auto shrink-0 flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-all",
              replay ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx border border-border"
            )}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 2v6h6" /><path d="M3 13a9 9 0 1 0 3-7.7L3 8" />
            </svg>
            Replay
          </button>
        </div>

        {replay && (
          <div className="shrink-0 border-b border-border bg-bg-sidebar/50 flex items-center gap-2 px-3 py-1.5 overflow-x-auto no-scrollbar">
            <button onClick={stepBack} title="Step back" className="w-7 h-7 shrink-0 rounded flex items-center justify-center text-tx-muted hover:text-tx hover:bg-border/50 transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zM20 6v12L9 12z" /></svg>
            </button>
            <button onClick={() => setPlaying((p) => !p)} title={playing ? "Pause" : "Play"} className="w-8 h-8 shrink-0 rounded-full flex items-center justify-center bg-brand-blue text-white hover:opacity-90 transition-opacity">
              {playing ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z" /></svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
              )}
            </button>
            <button onClick={stepFwd} title="Step forward" className="w-7 h-7 shrink-0 rounded flex items-center justify-center text-tx-muted hover:text-tx hover:bg-border/50 transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M16 6h2v12h-2zM4 6l11 6L4 18z" /></svg>
            </button>

            <input
              type="range"
              min={1}
              max={totalBars || 1}
              value={Math.min(replayIdx || 1, totalBars || 1)}
              onChange={(e) => { setPlaying(false); setReplayIdx(Number(e.target.value)); }}
              className="flex-1 min-w-[80px] accent-brand-blue cursor-pointer"
            />
            <span className="text-[10px] font-mono text-tx-muted shrink-0 tabular-nums">{replayIdx}/{totalBars}</span>

            <div className="flex items-center gap-0.5 shrink-0">
              {SPEEDS.map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={clsx(
                    "px-1.5 py-0.5 rounded text-[10px] font-semibold transition-colors",
                    speed === s ? "bg-brand-blue text-white" : "text-tx-muted hover:text-tx"
                  )}
                >
                  {s}×
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex-1 min-h-0">
          <TradingChart chartData={displayData} loading={isLoading} />
        </div>
      </div>
    </div>
  );
}
