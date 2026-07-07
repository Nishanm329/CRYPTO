import { useState, useEffect } from "react";
import clsx from "clsx";
import { tradingApi } from "../lib/trading-api";

function useSettings() {
  const defaults = {
    refreshInterval: "30",
    defaultSymbol: "BTCUSDT",
    defaultTimeframe: "1d",
    minConfidence: "45",
    showVolume: true,
    showBB: true,
    showVWAP: true,
    soundAlerts: false,
    compactMode: false,
    theme: "dark",
    visibleTimeframes: ["1m", "5m", "15m", "1h", "4h", "1d"],
    userProfile: "balanced",
    // Trading settings
    tradingEnabled: false,
    tradingMode: "PAPER", // PAPER or LIVE
    riskPerTrade: "2", // 1-5%
    binanceApiKey: "",
    binanceApiSecret: "",
    walletBalance: "10000",
  };
  const [settings, setSettings] = useState(defaults);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("app_settings") ?? "{}");
      setSettings(s => ({ ...s, ...stored }));
    } catch {}
  }, []);

  const update = (key, val) => setSettings(s => ({ ...s, [key]: val }));
  const save = () => {
    localStorage.setItem("app_settings", JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };
  const reset = () => { setSettings(defaults); localStorage.removeItem("app_settings"); };
  return { settings, update, save, reset, saved };
}

function Toggle({ checked, onChange, label, sub }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border/40">
      <div>
        <div className="text-xs font-semibold text-tx">{label}</div>
        {sub && <div className="text-[10px] text-tx-muted mt-0.5">{sub}</div>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={clsx(
          "w-10 h-5 rounded-full transition-all relative",
          checked ? "bg-brand-blue" : "bg-border"
        )}
      >
        <div className={clsx(
          "w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all",
          checked ? "left-5.5" : "left-0.5"
        )} style={{ left: checked ? "calc(100% - 18px)" : "2px" }} />
      </button>
    </div>
  );
}

function Select({ label, sub, value, onChange, options }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border/40">
      <div>
        <div className="text-xs font-semibold text-tx">{label}</div>
        {sub && <div className="text-[10px] text-tx-muted mt-0.5">{sub}</div>}
      </div>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="bg-bg border border-border rounded-lg px-3 py-1.5 text-xs text-tx outline-none focus:border-brand-blue transition-colors"
      >
        {options.map(([v,l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4 mb-4">
      <div className="text-[10px] font-semibold text-tx-muted uppercase tracking-widest mb-3">{title}</div>
      {children}
    </div>
  );
}

function TradingSettings({ settings, update, save }) {
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [keysStored, setKeysStored] = useState(false);
  const [storingKeys, setStoringKeys] = useState(false);
  const [revoking, setRevoking] = useState(false);

  // Check if keys are stored on backend
  useEffect(() => {
    const checkKeysStatus = async () => {
      try {
        const status = await tradingApi.getKeysStatus();
        setKeysStored(status.has_credentials);
      } catch (err) {
        console.error("Failed to check keys status:", err);
      }
    };
    checkKeysStatus();
  }, []);

  const handleValidateAndStore = async () => {
    if (!settings.binanceApiKey || !settings.binanceApiSecret) {
      setValidationResult({ error: "API key and secret are required" });
      return;
    }

    setValidating(true);
    try {
      // First validate the keys
      const result = await tradingApi.validateKeys(
        settings.binanceApiKey,
        settings.binanceApiSecret
      );

      if (result.valid) {
        // Store keys securely on backend
        setStoringKeys(true);
        await tradingApi.storeKeys(
          settings.binanceApiKey,
          settings.binanceApiSecret
        );
        setKeysStored(true);
        setStoringKeys(false);

        // Clear from frontend memory for security
        update("binanceApiKey", "");
        update("binanceApiSecret", "");

        setValidationResult({
          valid: true,
          message: "✓ Keys validated and stored securely on server",
          balance_usdt: result.balance_usdt,
        });
      } else {
        setValidationResult(result);
      }
    } catch (err) {
      setValidationResult({ error: err.message });
    } finally {
      setValidating(false);
      setStoringKeys(false);
    }
  };

  const handleRevokeKeys = async () => {
    if (!confirm("Are you sure you want to revoke Binance API keys? Trading will be disabled.")) {
      return;
    }

    setRevoking(true);
    try {
      await tradingApi.revokeKeys();
      setKeysStored(false);
      setValidationResult({
        valid: false,
        message: "Keys have been revoked",
      });
    } catch (err) {
      setValidationResult({ error: err.message });
    } finally {
      setRevoking(false);
    }
  };

  return (
    <>
      <Section title="Trading Mode">
        <div className="flex items-center gap-3 py-3 border-b border-border/40">
          <div>
            <div className="text-xs font-semibold text-tx">Mode</div>
            <div className="text-[10px] text-tx-muted mt-0.5">Paper trading (simulated) or live trading</div>
          </div>
          <div className="flex gap-2 ml-auto">
            {["PAPER", "LIVE"].map((mode) => (
              <button
                key={mode}
                onClick={() => update("tradingMode", mode)}
                className={clsx(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border",
                  settings.tradingMode === mode
                    ? "bg-brand-blue border-brand-blue text-white"
                    : "border-border text-tx-muted hover:border-border-light"
                )}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>

        <Toggle
          label="Trading enabled"
          sub="Enable/disable trading features"
          checked={settings.tradingEnabled}
          onChange={v => update("tradingEnabled", v)}
        />
      </Section>

      {settings.tradingEnabled && (
        <>
          <Section title="Risk Management">
            <div className="py-3 border-b border-border/40">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-xs font-semibold text-tx">Risk per trade</div>
                  <div className="text-[10px] text-tx-muted mt-0.5">Percentage of wallet</div>
                </div>
                <div className="text-xs font-bold text-brand-blue">{settings.riskPerTrade}%</div>
              </div>
              <input
                type="range"
                min="1"
                max="5"
                step="0.5"
                value={settings.riskPerTrade}
                onChange={(e) => update("riskPerTrade", e.target.value)}
                className="w-full h-1.5 bg-border rounded-lg appearance-none cursor-pointer"
                style={{
                  background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${(parseFloat(settings.riskPerTrade) / 5) * 100}%, #404040 ${(parseFloat(settings.riskPerTrade) / 5) * 100}%, #404040 100%)`
                }}
              />
            </div>

            <div className="py-3">
              <div className="text-xs font-semibold text-tx mb-2">Estimated wallet balance</div>
              <div className="flex items-center">
                <span className="text-xs text-tx-muted mr-2">$</span>
                <input
                  type="number"
                  value={settings.walletBalance}
                  onChange={(e) => update("walletBalance", e.target.value)}
                  className="flex-1 bg-bg border border-border rounded-lg px-3 py-1.5 text-xs text-tx outline-none focus:border-brand-blue transition-colors"
                />
              </div>
              <div className="text-[10px] text-tx-muted mt-2">
                Position size per trade: ~${(parseFloat(settings.walletBalance) * (parseFloat(settings.riskPerTrade) / 100)).toFixed(0)}
              </div>
            </div>
          </Section>

          <Section title="Binance API Keys">
            <div className="mb-3 p-3 bg-brand-red/10 border border-brand-red/30 rounded-lg">
              <div className="text-[10px] text-brand-red font-semibold">⚠️ Security Information</div>
              <div className="text-[10px] text-brand-red mt-1 space-y-1">
                <div>• Only grant "Spot Trading" permissions on Binance</div>
                <div>• Keys are encrypted and stored securely on our server</div>
                <div>• Never share your API keys with anyone</div>
              </div>
            </div>

            {keysStored ? (
              <div className="bg-brand-green/10 border border-brand-green/30 rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-brand-green">✓ Keys Stored Securely</div>
                  <span className="text-[10px] text-brand-green">Server-encrypted</span>
                </div>
                <p className="text-[10px] text-brand-green/80 mb-3">
                  Your API keys are encrypted and stored on our secure server. They are not stored in your browser.
                </p>
                <button
                  onClick={handleRevokeKeys}
                  disabled={revoking}
                  className="w-full py-1.5 px-3 rounded-lg text-xs font-semibold text-brand-red hover:text-brand-red/80 border border-brand-red/30 hover:border-brand-red transition-all"
                >
                  {revoking ? "Revoking..." : "Revoke Keys"}
                </button>
              </div>
            ) : (
              <>
                <div className="py-3 border-b border-border/40">
                  <div className="text-xs font-semibold text-tx mb-2">API Key</div>
                  <input
                    type="password"
                    placeholder="Enter your Binance API key"
                    value={settings.binanceApiKey}
                    onChange={(e) => update("binanceApiKey", e.target.value)}
                    className="w-full bg-bg border border-border rounded-lg px-3 py-1.5 text-xs text-tx outline-none focus:border-brand-blue transition-colors font-mono"
                  />
                  <div className="text-[10px] text-tx-muted mt-1">
                    Get from: Binance → Account → API Management
                  </div>
                </div>

                <div className="py-3 border-b border-border/40">
                  <div className="text-xs font-semibold text-tx mb-2">API Secret</div>
                  <input
                    type="password"
                    placeholder="Enter your Binance API secret"
                    value={settings.binanceApiSecret}
                    onChange={(e) => update("binanceApiSecret", e.target.value)}
                    className="w-full bg-bg border border-border rounded-lg px-3 py-1.5 text-xs text-tx outline-none focus:border-brand-blue transition-colors font-mono"
                  />
                  <div className="text-[10px] text-tx-muted mt-1">
                    Keep this secret! Never share or expose it.
                  </div>
                </div>

                <div className="py-3">
                  <button
                    onClick={handleValidateAndStore}
                    disabled={validating || storingKeys || !settings.binanceApiKey || !settings.binanceApiSecret}
                    className={clsx(
                      "w-full py-2 rounded-lg text-xs font-semibold transition-all text-white",
                      validating || storingKeys
                        ? "bg-brand-blue/50 cursor-not-allowed"
                        : "bg-brand-blue hover:bg-blue-500"
                    )}
                  >
                    {validating ? "Validating..." : storingKeys ? "Storing securely..." : "Validate & Store"}
                  </button>
                </div>

                {validationResult && (
                  <div className={clsx(
                    "mt-2 p-3 rounded text-[10px] border",
                    validationResult.valid || validationResult.message?.includes("✓")
                      ? "bg-brand-green/10 text-brand-green border-brand-green/30"
                      : "bg-brand-red/10 text-brand-red border-brand-red/30"
                  )}>
                    <div className="font-semibold mb-1">
                      {validationResult.valid ? "✓ Success" : "✗ Error"}
                    </div>
                    <div>
                      {validationResult.message
                        || (validationResult.valid
                          ? `Connected! Balance: $${validationResult.balance_usdt?.toLocaleString()}`
                          : validationResult.error || "Connection failed")}
                    </div>
                  </div>
                )}
              </>
            )}
          </Section>
        </>
      )}
    </>
  );
}

export default function SettingsView() {
  const { settings, update, save, reset, saved } = useSettings();

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 border-b border-border px-5 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-sm font-bold text-tx">Settings</h1>
          <p className="text-xs text-tx-muted mt-0.5">Configure your trading dashboard preferences.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={reset} className="px-3 py-1.5 rounded-lg text-xs text-tx-muted hover:text-tx border border-border hover:border-border-light transition-all">
            Reset defaults
          </button>
          <button
            onClick={save}
            className={clsx(
              "px-4 py-1.5 rounded-lg text-xs font-bold transition-all",
              saved ? "bg-brand-green text-white" : "bg-brand-blue text-white hover:bg-blue-500"
            )}
          >
            {saved ? "✓ Saved" : "Save Changes"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-5 max-w-2xl mx-auto w-full">
        <Section title="Data & Refresh">
          <Select
            label="Auto-refresh interval"
            sub="How often live data is fetched"
            value={settings.refreshInterval}
            onChange={v => update("refreshInterval", v)}
            options={[["10","10 seconds"],["30","30 seconds"],["60","1 minute"],["300","5 minutes"]]}
          />
          <Select
            label="Default symbol"
            sub="Coin shown on startup"
            value={settings.defaultSymbol}
            onChange={v => update("defaultSymbol", v)}
            options={[["BTCUSDT","BTC/USDT"],["ETHUSDT","ETH/USDT"],["SOLUSDT","SOL/USDT"],["BNBUSDT","BNB/USDT"]]}
          />
          <Select
            label="Default timeframe"
            sub="Chart timeframe on startup"
            value={settings.defaultTimeframe}
            onChange={v => update("defaultTimeframe", v)}
            options={[["1m","1 minute"],["5m","5 minutes"],["15m","15 minutes"],["1h","1 hour"],["4h","4 hours"],["1d","1 day"]]}
          />
        </Section>

        <Section title="Scanner">
          <Select
            label="Minimum confidence"
            sub="Only show signals above this threshold"
            value={settings.minConfidence}
            onChange={v => update("minConfidence", v)}
            options={[["30","30%"],["40","40%"],["45","45%"],["50","50%"],["60","60%"],["70","70%"]]}
          />
        </Section>

        <Section title="Chart Indicators">
          <Toggle label="Bollinger Bands" sub="Show BB overlay on chart" checked={settings.showBB} onChange={v => update("showBB", v)} />
          <Toggle label="VWAP" sub="Show Volume Weighted Average Price" checked={settings.showVWAP} onChange={v => update("showVWAP", v)} />
          <Toggle label="Volume histogram" sub="Show coloured volume bars" checked={settings.showVolume} onChange={v => update("showVolume", v)} />
        </Section>

        <Section title="Appearance">
          <Toggle label="Compact mode" sub="Reduce padding for more data density" checked={settings.compactMode} onChange={v => update("compactMode", v)} />
          <Toggle label="Sound alerts" sub="Play a sound when a signal fires" checked={settings.soundAlerts} onChange={v => update("soundAlerts", v)} />
        </Section>

        <Section title="Trader Profile">
          <div className="space-y-2">
            {[
              { id: "daytrader", name: "Day Trader", desc: "Fast-moving, short timeframes (1m-1h)" },
              { id: "swing", name: "Swing Trader", desc: "Medium-term positions (4h-1d)" },
              { id: "position", name: "Position Trader", desc: "Long-term holdings (1d-1w)" },
            ].map(({ id, name, desc }) => (
              <button
                key={id}
                onClick={() => {
                  update("userProfile", id);
                  const tfMap = {
                    daytrader: ["1m", "5m", "15m", "1h"],
                    swing: ["4h", "1d", "3d"],
                    position: ["1d", "3d", "1w"],
                  };
                  update("visibleTimeframes", tfMap[id]);
                }}
                className={clsx(
                  "w-full text-left px-3 py-2 rounded-lg border transition-all",
                  settings.userProfile === id
                    ? "border-brand-blue bg-brand-blue/10"
                    : "border-border hover:border-border-light"
                )}
              >
                <div className="text-xs font-semibold text-tx">{name}</div>
                <div className="text-[10px] text-tx-muted mt-0.5">{desc}</div>
              </button>
            ))}
          </div>
        </Section>

        <Section title="Visible Timeframes">
          <div className="grid grid-cols-4 gap-2">
            {["1m", "5m", "15m", "1h", "4h", "1d", "3d", "1w"].map(tf => (
              <button
                key={tf}
                onClick={() => {
                  const current = settings.visibleTimeframes || [];
                  if (current.includes(tf)) {
                    update("visibleTimeframes", current.filter(t => t !== tf));
                  } else {
                    update("visibleTimeframes", [...current, tf]);
                  }
                }}
                className={clsx(
                  "px-2 py-1.5 rounded text-xs font-semibold transition-all border",
                  (settings.visibleTimeframes || []).includes(tf)
                    ? "border-brand-blue bg-brand-blue text-white"
                    : "border-border text-tx-muted hover:border-border-light"
                )}
              >
                {tf}
              </button>
            ))}
          </div>
        </Section>

        <TradingSettings settings={settings} update={update} save={save} />

        <Section title="About">
          <div className="text-xs text-tx-muted space-y-1.5">
            <div className="flex justify-between"><span>Version</span><span className="text-tx">2.0.0</span></div>
            <div className="flex justify-between"><span>Data source</span><span className="text-tx">Binance Public API</span></div>
            <div className="flex justify-between"><span>News source</span><span className="text-tx">CryptoCompare</span></div>
            <div className="flex justify-between"><span>Sentiment</span><span className="text-tx">Alternative.me F&G</span></div>
            <div className="flex justify-between"><span>Backend</span><span className="text-tx">FastAPI · localhost:8000</span></div>
          </div>
        </Section>
      </div>
    </div>
  );
}
