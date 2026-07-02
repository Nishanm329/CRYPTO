import { useState, useEffect } from "react";
import clsx from "clsx";
import { api } from "../lib/api";

const FREQUENCIES = [
  ["15m", "Every 15 min"],
  ["1h", "Hourly"],
  ["4h", "Every 4 hours"],
  ["1d", "Daily"],
  ["1w", "Weekly"],
];

const TFS = ["1m", "5m", "15m", "1h", "4h", "1d", "3d", "1w"];

// Which filter controls each component's digest supports.
const FILTER_FIELDS = {
  signals: ["timeframe", "min_confidence", "direction", "top_n"],
  scanner: ["timeframe", "min_confidence", "direction", "top_n"],
  market: ["top_n"],
  "track-record": [],
};

function MailIcon() {
  return (
    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 7l9 6 9-6" />
    </svg>
  );
}

export default function EmailScheduleButton({ component, label = "Email schedule" }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title={label}
        className="p-1.5 rounded-lg text-tx-muted hover:text-tx hover:bg-border transition-all"
      >
        <MailIcon />
      </button>
      {open && <EmailScheduleModal component={component} onClose={() => setOpen(false)} />}
    </>
  );
}

function EmailScheduleModal({ component, onClose }) {
  const [cfg, setCfg] = useState(null);
  const [smtpOk, setSmtpOk] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [sending, setSending] = useState(false);
  const [msg, setMsg] = useState(null);

  const fields = FILTER_FIELDS[component] || [];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [conf, status] = await Promise.all([
          api.emailConfig(component),
          api.emailStatus().catch(() => ({ smtp_configured: true })),
        ]);
        if (cancelled) return;
        setCfg(conf);
        setSmtpOk(status.smtp_configured);
      } catch (e) {
        if (!cancelled) setMsg({ error: e.message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [component]);

  const update = (patch) => setCfg((c) => ({ ...c, ...patch }));
  const updateFilter = (key, val) =>
    setCfg((c) => ({ ...c, filters: { ...c.filters, [key]: val } }));

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const next = await api.saveEmailConfig(component, {
        enabled: cfg.enabled,
        recipient: cfg.recipient,
        frequency: cfg.frequency,
        filters: cfg.filters,
      });
      setCfg(next);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setMsg({ error: e.message });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!cfg?.recipient) {
      setMsg({ error: "Add a recipient email first." });
      return;
    }
    setSending(true);
    setMsg(null);
    try {
      // Persist current settings before sending so the test reflects them.
      await api.saveEmailConfig(component, {
        enabled: cfg.enabled,
        recipient: cfg.recipient,
        frequency: cfg.frequency,
        filters: cfg.filters,
      });
      await api.sendEmailTest(component);
      setMsg({ ok: `Sent to ${cfg.recipient}` });
    } catch (e) {
      setMsg({ error: e.message });
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-bg-card border border-border rounded-2xl shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div className="flex items-center gap-2 text-tx">
            <MailIcon />
            <span className="text-sm font-bold capitalize">{component.replace("-", " ")} email</span>
          </div>
          <button onClick={onClose} className="text-tx-muted hover:text-tx text-lg leading-none">
            ×
          </button>
        </div>

        {!cfg ? (
          <div className="flex items-center justify-center h-32">
            <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="p-5 space-y-4">
            {!smtpOk && (
              <div className="p-3 bg-brand-red/10 border border-brand-red/30 rounded-lg text-[10px] text-brand-red">
                ⚠️ Email sending isn't configured on the server yet (SMTP env vars). You can save a
                schedule now; delivery starts once SMTP is set.
              </div>
            )}

            {/* Enable */}
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-semibold text-tx">Email me this</div>
                <div className="text-[10px] text-tx-muted mt-0.5">Send this component on a schedule</div>
              </div>
              <button
                onClick={() => update({ enabled: !cfg.enabled })}
                className={clsx(
                  "w-10 h-5 rounded-full transition-all relative",
                  cfg.enabled ? "bg-brand-blue" : "bg-border"
                )}
              >
                <div
                  className="w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all"
                  style={{ left: cfg.enabled ? "calc(100% - 18px)" : "2px" }}
                />
              </button>
            </div>

            {/* Recipient */}
            <div>
              <label className="text-xs font-semibold text-tx">Recipient</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={cfg.recipient}
                onChange={(e) => update({ recipient: e.target.value })}
                className="mt-1 w-full bg-bg border border-border rounded-lg px-3 py-1.5 text-xs text-tx outline-none focus:border-brand-blue transition-colors"
              />
            </div>

            {/* Frequency */}
            <div>
              <label className="text-xs font-semibold text-tx">Frequency</label>
              <select
                value={cfg.frequency}
                onChange={(e) => update({ frequency: e.target.value })}
                className="mt-1 w-full bg-bg border border-border rounded-lg px-3 py-1.5 text-xs text-tx outline-none focus:border-brand-blue transition-colors"
              >
                {FREQUENCIES.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </div>

            {/* Filters */}
            {fields.includes("timeframe") && (
              <div>
                <label className="text-xs font-semibold text-tx">Timeframe</label>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {TFS.map((tf) => (
                    <button
                      key={tf}
                      onClick={() => updateFilter("timeframe", tf)}
                      className={clsx(
                        "px-2 py-1 rounded text-xs font-semibold transition-all border",
                        cfg.filters.timeframe === tf
                          ? "border-brand-blue bg-brand-blue text-white"
                          : "border-border text-tx-muted hover:border-border-light"
                      )}
                    >
                      {tf.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {fields.includes("direction") && (
              <div>
                <label className="text-xs font-semibold text-tx">Direction</label>
                <div className="mt-1 flex gap-1.5">
                  {["ALL", "LONG", "SHORT"].map((d) => (
                    <button
                      key={d}
                      onClick={() => updateFilter("direction", d)}
                      className={clsx(
                        "px-3 py-1 rounded text-xs font-semibold transition-all border",
                        (cfg.filters.direction || "ALL") === d
                          ? "border-brand-blue bg-brand-blue text-white"
                          : "border-border text-tx-muted hover:border-border-light"
                      )}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {fields.includes("min_confidence") && (
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-tx">Minimum confidence</label>
                  <span className="text-xs font-bold text-brand-blue">{cfg.filters.min_confidence}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={cfg.filters.min_confidence}
                  onChange={(e) => updateFilter("min_confidence", parseInt(e.target.value, 10))}
                  className="mt-2 w-full h-1.5 bg-border rounded-lg appearance-none cursor-pointer"
                />
              </div>
            )}

            {fields.includes("top_n") && (
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-tx">Rows to include</label>
                  <span className="text-xs font-bold text-brand-blue">{cfg.filters.top_n}</span>
                </div>
                <input
                  type="range"
                  min="3"
                  max="25"
                  step="1"
                  value={cfg.filters.top_n}
                  onChange={(e) => updateFilter("top_n", parseInt(e.target.value, 10))}
                  className="mt-2 w-full h-1.5 bg-border rounded-lg appearance-none cursor-pointer"
                />
              </div>
            )}

            {msg && (
              <div
                className={clsx(
                  "p-2.5 rounded-lg text-[10px] border",
                  msg.ok
                    ? "bg-brand-green/10 text-brand-green border-brand-green/30"
                    : "bg-brand-red/10 text-brand-red border-brand-red/30"
                )}
              >
                {msg.ok || msg.error}
              </div>
            )}

            <div className="flex items-center gap-2 pt-1">
              <button
                onClick={handleTest}
                disabled={sending}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold text-tx-muted hover:text-tx border border-border hover:border-border-light transition-all disabled:opacity-50"
              >
                {sending ? "Sending…" : "Send test now"}
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className={clsx(
                  "ml-auto px-4 py-1.5 rounded-lg text-xs font-bold transition-all text-white",
                  saved ? "bg-brand-green" : "bg-brand-blue hover:bg-blue-500"
                )}
              >
                {saved ? "✓ Saved" : saving ? "Saving…" : "Save schedule"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
