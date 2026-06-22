import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { createChart, ColorType, CrosshairMode, LineStyle } from "lightweight-charts";
import { formatPrice } from "../lib/api";
import clsx from "clsx";

const BASE_OPTS = {
  layout: {
    background: { type: ColorType.Solid, color: "#13141f" },
    textColor: "#5a5e7a",
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 11,
  },
  grid: {
    vertLines: { color: "#13141f" },
    horzLines: { color: "#1a1b2e" },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: "#252640", labelBackgroundColor: "#1a1b2e" },
    horzLine: { color: "#252640", labelBackgroundColor: "#1a1b2e" },
  },
  rightPriceScale: { borderColor: "#1e1f30" },
  timeScale: { borderColor: "#1e1f30", timeVisible: true, secondsVisible: false },
  handleScroll: true,
  handleScale: true,
};

const TOOLBAR_TOOLS = [
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z" />
      </svg>
    ),
  },
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
      </svg>
    ),
  },
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
    ),
  },
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="3" width="18" height="18" rx="2" />
      </svg>
    ),
  },
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    ),
  },
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
      </svg>
    ),
  },
  { separator: true },
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        <line x1="11" y1="8" x2="11" y2="14" /><line x1="8" y1="11" x2="14" y2="11" />
      </svg>
    ),
  },
  {
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        <line x1="8" y1="11" x2="14" y2="11" />
      </svg>
    ),
  },
];

const TIME_RANGES = ["1D", "5D", "1M", "3M", "6M", "YTD", "1Y", "5Y", "All"];

function LegendChip({ color, label, value }) {
  if (value == null) return null;
  return (
    <span className="flex items-center gap-1 text-[10px] font-mono">
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
      <span className="text-tx-muted">{label}</span>
      <span style={{ color }}>{typeof value === "number" ? formatPrice(value) : value}</span>
    </span>
  );
}

export default function TradingChart({ chartData, loading, className = "" }) {
  const mainContainerRef = useRef(null);
  const rsiContainerRef = useRef(null);
  const macdContainerRef = useRef(null);
  const stochContainerRef = useRef(null);
  const mainChartRef = useRef(null);
  const rsiChartRef = useRef(null);
  const macdChartRef = useRef(null);
  const stochChartRef = useRef(null);
  const seriesRef = useRef({});
  const perfMarkerRef = useRef({});

  const [hoveredBar, setHoveredBar] = useState(null);
  const [lv, setLv] = useState(null);
  const [activeIndicators, setActiveIndicators] = useState({ ema: true, bb: true, vwap: true, ew: false, rsi: true, macd: true, stoch: true });
  const [selectedTool, setSelectedTool] = useState(0);

  const syncCrosshair = useCallback((src, others, param) => {
    for (const c of others) {
      if (!c || c === src) continue;
      if (param.point) {
        try { c.setCrosshairPosition(param.point.x, param.point.y, Object.values(Object.fromEntries(param.seriesData || []))[0]); } catch {}
      } else {
        try { c.clearCrosshairPosition(); } catch {}
      }
    }
  }, []);

  useEffect(() => {
    if (!mainContainerRef.current) {
      console.warn('[TradingChart] mainContainerRef not ready');
      return;
    }

    // Defer to next frame to ensure browser has computed layout
    let frameId = requestAnimationFrame(() => {
      try {
        const width = mainContainerRef.current?.clientWidth || 0;
        const height = 340;

        if (width === 0) {
          console.warn('[TradingChart] Container width is 0, will retry on resize');
        }

        console.log(`[TradingChart] Creating chart with dimensions: ${width}x${height}`);

        // ── Main Chart ──
        const mc = createChart(mainContainerRef.current, {
          ...BASE_OPTS,
          width: width || 600,
          height,
          timeScale: { ...BASE_OPTS.timeScale, visible: false },
        });
        mainChartRef.current = mc;

        const candle = mc.addCandlestickSeries({
          upColor: "#00c896", downColor: "#ef4444",
          borderUpColor: "#00c896", borderDownColor: "#ef4444",
          wickUpColor: "#00c896", wickDownColor: "#ef4444",
        });
        seriesRef.current.candle = candle;

        seriesRef.current.ema7 = mc.addLineSeries({ color: "#facc15", lineWidth: 2, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        seriesRef.current.ema25 = mc.addLineSeries({ color: "#38bdf8", lineWidth: 2, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        seriesRef.current.bbUpper = mc.addLineSeries({ color: "rgba(100,160,255,0.6)", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        seriesRef.current.bbMiddle = mc.addLineSeries({ color: "rgba(100,160,255,0.3)", lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        seriesRef.current.bbLower = mc.addLineSeries({ color: "rgba(100,160,255,0.6)", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        seriesRef.current.vwap = mc.addLineSeries({ color: "#c084fc", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        seriesRef.current.ew = mc.addLineSeries({ color: "#eab308", lineWidth: 2, priceLineVisible: false, crosshairMarkerVisible: false, lastValueVisible: false, title: "" });
        seriesRef.current.volume = mc.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol" });
        mc.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

        mc.subscribeCrosshairMove((p) => {
          if (p.seriesData?.has(candle)) { const b = p.seriesData.get(candle); if (b) setHoveredBar(b); }
          syncCrosshair(mc, [rsiChartRef.current, macdChartRef.current, stochChartRef.current], p);
        });

        // ── RSI Chart ──
        const rc = createChart(rsiContainerRef.current, {
          ...BASE_OPTS,
          width: rsiContainerRef.current?.clientWidth || 600,
          height: 80,
          timeScale: { ...BASE_OPTS.timeScale, visible: false },
        });
        rsiChartRef.current = rc;
        seriesRef.current.rsi = rc.addLineSeries({ color: "#a855f7", lineWidth: 1.2, priceLineVisible: false, title: "" });
        seriesRef.current.rsiOB = rc.addLineSeries({ color: "rgba(239,68,68,0.35)", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        seriesRef.current.rsiOS = rc.addLineSeries({ color: "rgba(0,200,150,0.35)", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        rc.subscribeCrosshairMove((p) => syncCrosshair(rc, [mc, macdChartRef.current, stochChartRef.current], p));

        // ── MACD Chart ──
        const mcd = createChart(macdContainerRef.current, {
          ...BASE_OPTS,
          width: macdContainerRef.current?.clientWidth || 600,
          height: 80,
          timeScale: { ...BASE_OPTS.timeScale, visible: false },
        });
        macdChartRef.current = mcd;
        seriesRef.current.macdHist = mcd.addHistogramSeries({ priceLineVisible: false, title: "" });
        seriesRef.current.macdLine = mcd.addLineSeries({ color: "#f97316", lineWidth: 1.2, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        seriesRef.current.macdSignal = mcd.addLineSeries({ color: "#3d7fff", lineWidth: 1.2, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        mcd.subscribeCrosshairMove((p) => syncCrosshair(mcd, [mc, rc, stochChartRef.current], p));

        // ── StochRSI Chart ──
        const sc = createChart(stochContainerRef.current, {
          ...BASE_OPTS,
          width: stochContainerRef.current?.clientWidth || 600,
          height: 80,
          timeScale: { ...BASE_OPTS.timeScale, visible: true },
        });
        stochChartRef.current = sc;
        seriesRef.current.stochK = sc.addLineSeries({ color: "#3d7fff", lineWidth: 1.2, priceLineVisible: false, title: "" });
        seriesRef.current.stochD = sc.addLineSeries({ color: "#f97316", lineWidth: 1.2, priceLineVisible: false, crosshairMarkerVisible: false, title: "" });
        sc.subscribeCrosshairMove((p) => syncCrosshair(sc, [mc, rc, mcd], p));

        // Resize observer
        const ro = new ResizeObserver(() => {
          if (!mainContainerRef.current) return;
          try {
            const w = mainContainerRef.current.clientWidth;
            mc.applyOptions({ width: w });
            rc.applyOptions({ width: w });
            mcd.applyOptions({ width: w });
            sc.applyOptions({ width: w });
          } catch (e) {
            console.error('[TradingChart] Resize error:', e);
          }
        });
        ro.observe(mainContainerRef.current);

        console.log('[TradingChart] All charts initialized successfully');

        // Store cleanup function for when component unmounts
        seriesRef.current.cleanup = () => {
          try {
            ro.disconnect();
            // Try to remove charts, but ignore disposal errors during HMR
            try { mc.remove(); } catch (e) { if (!e.message.includes('disposed')) console.error('[TradingChart] Main chart cleanup:', e); }
            try { rc.remove(); } catch (e) { if (!e.message.includes('disposed')) console.error('[TradingChart] RSI chart cleanup:', e); }
            try { mcd.remove(); } catch (e) { if (!e.message.includes('disposed')) console.error('[TradingChart] MACD chart cleanup:', e); }
            try { sc.remove(); } catch (e) { if (!e.message.includes('disposed')) console.error('[TradingChart] Stoch chart cleanup:', e); }
            console.log('[TradingChart] Charts cleaned up');
          } catch (e) {
            console.error('[TradingChart] Cleanup error:', e);
          }
        };
      } catch (error) {
        console.error('[TradingChart] Chart initialization error:', error);
      }
    });

    return () => {
      cancelAnimationFrame(frameId);
      seriesRef.current.cleanup?.();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!chartData || !seriesRef.current.candle) return;
    const s = seriesRef.current;
    const startTime = performance.now();

    // Batch all series updates before fitting content
    try {
      s.candle.setData(chartData.bars.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close })));
      s.candle.setMarkers(activeIndicators.ema ? chartData.signals || [] : []);
      s.ema7.setData(activeIndicators.ema ? chartData.ema7 || [] : []);
      s.ema25.setData(activeIndicators.ema ? chartData.ema25 || [] : []);
      s.bbUpper.setData(activeIndicators.bb ? chartData.bb_upper || [] : []);
      s.bbMiddle.setData(activeIndicators.bb ? chartData.bb_middle || [] : []);
      s.bbLower.setData(activeIndicators.bb ? chartData.bb_lower || [] : []);
      s.vwap.setData(activeIndicators.vwap ? chartData.vwap || [] : []);
      s.ew.setData(activeIndicators.ew ? chartData.elliott_wave || [] : []);
      s.ew.setMarkers(activeIndicators.ew ? chartData.elliott_wave_markers || [] : []);
      s.volume.setData(chartData.volume || chartData.bars.map((b) => ({
        time: b.time, value: b.volume,
        color: b.close >= b.open ? "rgba(0,200,150,0.35)" : "rgba(239,68,68,0.35)",
      })));
      if (s.rsi && chartData.rsi?.length) {
        s.rsi.setData(chartData.rsi);
        s.rsiOB.setData(chartData.rsi.map((r) => ({ time: r.time, value: 70 })));
        s.rsiOS.setData(chartData.rsi.map((r) => ({ time: r.time, value: 30 })));
      }
      if (s.macdHist && chartData.macd_hist?.length) {
        s.macdHist.setData(chartData.macd_hist.map((d) => ({
          ...d, color: (d.value || 0) >= 0 ? "rgba(0,200,150,0.7)" : "rgba(239,68,68,0.7)",
        })));
        s.macdLine.setData(chartData.macd || []);
        s.macdSignal.setData(chartData.macd_signal || []);
      }
      if (s.stochK && chartData.stoch_k?.length) {
        s.stochK.setData(chartData.stoch_k);
        s.stochD.setData(chartData.stoch_d || []);
      }

      const dataUpdateMs = performance.now() - startTime;
      console.log(`[TradingChart] Data update took ${dataUpdateMs.toFixed(1)}ms (${chartData.bars?.length || 0} candles)`);

      // Defer fitContent() to next frame to batch layout recalculations
      const fitId = requestAnimationFrame(() => {
        const fitStart = performance.now();
        try {
          mainChartRef.current?.timeScale().fitContent();
          rsiChartRef.current?.timeScale().fitContent();
          macdChartRef.current?.timeScale().fitContent();
          stochChartRef.current?.timeScale().fitContent();
          console.log(`[TradingChart] fitContent took ${(performance.now() - fitStart).toFixed(1)}ms`);
        } catch (e) {
          console.error('[TradingChart] fitContent error:', e);
        }
      });

      if (chartData.latest_values) setLv(chartData.latest_values);

      return () => cancelAnimationFrame(fitId);
    } catch (error) {
      console.error('[TradingChart] Data update error:', error);
    }
  }, [chartData]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!chartData || !seriesRef.current) return;
    const s = seriesRef.current;

    // Only update series that changed - defer to next frame for batch
    requestAnimationFrame(() => {
      s.ema7?.setData(activeIndicators.ema ? chartData.ema7 || [] : []);
      s.ema25?.setData(activeIndicators.ema ? chartData.ema25 || [] : []);
      s.candle?.setMarkers(activeIndicators.ema ? chartData.signals || [] : []);

      if (activeIndicators.bb) {
        s.bbUpper?.setData(chartData.bb_upper || []);
        s.bbMiddle?.setData(chartData.bb_middle || []);
        s.bbLower?.setData(chartData.bb_lower || []);
      } else {
        s.bbUpper?.setData([]);
        s.bbMiddle?.setData([]);
        s.bbLower?.setData([]);
      }

      s.vwap?.setData(activeIndicators.vwap ? chartData.vwap || [] : []);

      s.ew?.setData(activeIndicators.ew ? chartData.elliott_wave || [] : []);
      s.ew?.setMarkers(activeIndicators.ew ? chartData.elliott_wave_markers || [] : []);

      // Only fit if indicators changed (not on initial load)
      try {
        mainChartRef.current?.timeScale().fitContent();
      } catch (e) {
        if (!e.message.includes('disposed')) console.error('[TradingChart] fitContent error:', e);
      }
    });
  }, [activeIndicators.ema, activeIndicators.bb, activeIndicators.vwap, activeIndicators.ew]); // eslint-disable-line react-hooks/exhaustive-deps

  const bar = hoveredBar;

  return (
    <div className={`flex flex-col bg-bg-card border border-border rounded-xl overflow-hidden w-full ${className || 'h-full'}`}>
      {/* ── Chart info bar ── */}
      <div className="px-4 py-2 border-b border-border flex flex-wrap items-center gap-x-4 gap-y-1 shrink-0">
        <span className="text-xs text-tx-muted font-medium">
          {chartData?.symbol ?? "—"} ·{" "}
          <span className="text-tx font-semibold">{chartData?.timeframe?.toUpperCase() ?? "—"}</span>
          {" · BINANCE"}
        </span>

        {bar && (
          <div className="flex items-center gap-3 text-[11px] font-mono">
            <span className="text-tx-muted">O <span className="text-tx">{formatPrice(bar.open)}</span></span>
            <span className="text-tx-muted">H <span className="text-brand-green">{formatPrice(bar.high)}</span></span>
            <span className="text-tx-muted">L <span className="text-brand-red">{formatPrice(bar.low)}</span></span>
            <span className="text-tx-muted">C <span className="text-tx font-semibold">{formatPrice(bar.close)}</span></span>
          </div>
        )}

        <div className="flex items-center gap-3 ml-auto">
          {[
            { key: "ema", label: "EMA 7/25" },
            { key: "bb", label: "BB" },
            { key: "vwap", label: "VWAP" },
            { key: "ew", label: "EW" },
            { key: "rsi", label: "RSI" },
            { key: "macd", label: "MACD" },
            { key: "stoch", label: "Stoch" },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveIndicators((p) => ({ ...p, [key]: !p[key] }))}
              className={clsx(
                "text-[10px] font-semibold px-1.5 py-0.5 rounded transition-colors",
                activeIndicators[key] ? "text-brand-blue bg-brand-blue/10" : "text-tx-dim hover:text-tx-muted"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Main area: left toolbar + chart ── */}
      <div className="flex flex-1 w-full overflow-hidden">
        {/* Left drawing toolbar */}
        <div className="w-9 shrink-0 flex flex-col items-center gap-0.5 py-2 border-r border-border bg-bg-card">
          {TOOLBAR_TOOLS.map((tool, i) =>
            tool.separator ? (
              <div key={i} className="w-5 h-px bg-border my-1" />
            ) : (
              <button
                key={i}
                onClick={() => setSelectedTool(i)}
                className={clsx(
                  "w-7 h-7 rounded flex items-center justify-center transition-colors",
                  selectedTool === i
                    ? "bg-brand-blue/15 text-brand-blue"
                    : "text-tx-dim hover:text-tx-muted hover:bg-border/50"
                )}
              >
                {tool.icon}
              </button>
            )
          )}
        </div>

        {/* Chart content */}
        <div className="flex-1 min-w-0 w-full flex flex-col relative overflow-hidden">
          {/* Indicator legend overlay */}
          <div className="absolute top-1 left-2 z-10 flex flex-wrap items-center gap-x-3 gap-y-0.5">
            {activeIndicators.ema && (
              <>
                <LegendChip color="#facc15" label="EMA 7" value={lv?.ema7} />
                <LegendChip color="#38bdf8" label="EMA 25" value={lv?.ema25} />
                <span className="flex items-center gap-1 text-[10px] font-mono text-tx-muted">
                  <span className="text-brand-green">▲</span>/<span className="text-brand-red">▼</span> cross
                </span>
              </>
            )}
            {activeIndicators.bb && lv?.bb_upper && (
              <LegendChip color="rgba(100,160,255,0.9)" label="BB 20,2" value={lv.bb_upper} />
            )}
            {activeIndicators.vwap && <LegendChip color="#c084fc" label="VWAP" value={lv?.vwap} />}
          </div>

          {/* Candlestick chart */}
          <div ref={mainContainerRef} className="w-full flex-1 min-h-0" />

          {/* RSI subchart */}
          {activeIndicators.rsi && (
            <div className="border-t border-border shrink-0 h-24">
              <div className="px-3 pt-1 flex items-center gap-3 text-[10px] text-tx-muted">
                <span className="text-tx-muted">RSI 14 close</span>
                {lv?.rsi != null && (
                  <span className="font-mono font-bold" style={{
                    color: lv.rsi > 70 ? "#ef4444" : lv.rsi < 30 ? "#00c896" : "#a855f7"
                  }}>
                    {lv.rsi.toFixed(2)}
                  </span>
                )}
              </div>
              <div ref={rsiContainerRef} className="w-full h-20" />
            </div>
          )}

          {/* MACD subchart */}
          {activeIndicators.macd && (
            <div className="border-t border-border shrink-0 h-24">
              <div className="px-3 pt-1 flex items-center gap-3 text-[10px] text-tx-muted">
                <span>MACD 12 26 close 9</span>
                {lv?.macd != null && (
                  <>
                    <span className="font-mono text-[#f97316]">{lv.macd.toFixed(2)}</span>
                    <span className="font-mono text-[#3d7fff]">{lv.macd_signal?.toFixed(2)}</span>
                    <span className="font-mono font-bold" style={{ color: (lv.macd_hist || 0) >= 0 ? "#00c896" : "#ef4444" }}>
                      {lv.macd_hist?.toFixed(2)}
                    </span>
                  </>
                )}
              </div>
              <div ref={macdContainerRef} className="w-full h-20" />
            </div>
          )}

          {/* StochRSI subchart */}
          {activeIndicators.stoch && (
            <div className="border-t border-border shrink-0 h-24">
              <div className="px-3 pt-1 flex items-center gap-3 text-[10px] text-tx-muted">
                <span>Stoch RSI 14 14 3 3</span>
                {lv?.stoch_k != null && (
                  <>
                    <span className="font-mono text-[#3d7fff]">{lv.stoch_k.toFixed(2)}</span>
                    <span className="font-mono text-[#f97316]">{lv.stoch_d?.toFixed(2)}</span>
                  </>
                )}
              </div>
              <div ref={stochContainerRef} className="w-full h-20" />
            </div>
          )}

          {/* Bottom time range bar */}
          <div className="border-t border-border px-3 py-1.5 flex items-center gap-0.5 shrink-0">
            {TIME_RANGES.map((r) => (
              <button
                key={r}
                className="px-2 py-0.5 text-[10px] text-tx-dim hover:text-tx-muted hover:bg-border/50 rounded transition-colors"
              >
                {r}
              </button>
            ))}
            <div className="flex-1" />
            <span className="text-[10px] text-tx-dim font-mono" suppressHydrationWarning>
              {new Date().toUTCString().slice(17, 25)} UTC
            </span>
            <div className="flex items-center gap-1 ml-3">
              {["%" , "log", "auto"].map((t) => (
                <button key={t} className="text-[10px] text-tx-dim hover:text-tx-muted px-1">{t}</button>
              ))}
            </div>
          </div>

          {/* Loading overlay */}
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-bg-card/80 z-20 backdrop-blur-sm">
              <div className="flex flex-col items-center gap-3">
                <div className="w-6 h-6 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
                <div className="text-center">
                  <span className="text-xs font-medium text-tx">Loading chart</span>
                  <div className="text-[10px] text-tx-dim mt-1">~2-3 seconds</div>
                </div>
              </div>
            </div>
          )}

          {!loading && !chartData && (
            <div className="absolute inset-0 flex items-center justify-center text-tx-muted text-sm">
              Select a coin to view chart
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
