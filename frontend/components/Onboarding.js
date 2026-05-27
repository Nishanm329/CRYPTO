import { useState, useEffect } from "react";
import clsx from "clsx";

const STEPS = [
  {
    title: "Welcome to CryptoExpert",
    desc: "Your AI-powered trading dashboard for real-time market analysis.",
    icon: "🚀",
    highlight: null,
  },
  {
    title: "Understand Signals",
    desc: "Green ↑ BUY signals mean bullish momentum. Red ↓ SELL signals indicate bearish pressure. Confidence % shows our model's certainty.",
    icon: "📊",
    highlight: "signals",
  },
  {
    title: "Chart Analysis",
    desc: "Use the main chart to analyze price action. Click timeframe buttons to switch between 1m, 5m, 15m, 1h, 4h, 1d, 3d, 1w views.",
    icon: "📈",
    highlight: "chart",
  },
  {
    title: "Scanner & Top Signals",
    desc: "Top Signals shows the best opportunities right now. The Scanner digs deeper into all coin pairs across your selected timeframe.",
    icon: "🔍",
    highlight: "scanner",
  },
  {
    title: "Portfolio Tracking",
    desc: "Add your holdings to track P&L in real-time. All data is saved locally in your browser—never sent to our servers.",
    icon: "💼",
    highlight: "portfolio",
  },
  {
    title: "Price Alerts",
    desc: "Set alerts for specific price levels. Get notified when coins hit your targets. Perfect for trading while away.",
    icon: "🔔",
    highlight: "alerts",
  },
  {
    title: "Customize Settings",
    desc: "Choose your trader profile (Day/Swing/Position), customize visible timeframes, and adjust indicator preferences.",
    icon: "⚙️",
    highlight: "settings",
  },
  {
    title: "Keyboard Shortcuts",
    desc: "Press C for Chart, S for Signals, P for Portfolio, A for Alerts, M for Market, N for News, D for Dashboard.",
    icon: "⌨️",
    highlight: null,
  },
];

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(0);
  const [shown, setShown] = useState(true);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem("onboarding_dismissed");
    if (dismissed) {
      setShown(false);
      onComplete?.();
    }
  }, [onComplete]);

  const handleNext = () => {
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    } else {
      handleComplete();
    }
  };

  const handleComplete = () => {
    localStorage.setItem("onboarding_dismissed", "true");
    setShown(false);
    onComplete?.();
  };

  if (!shown || dismissed) return null;

  const current = STEPS[step];

  return (
    <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
      <div className="bg-bg-card border border-border rounded-xl p-8 max-w-md w-full shadow-2xl animate-in fade-in scale-in duration-300">
        {/* Close button */}
        <button
          onClick={handleComplete}
          className="absolute top-4 right-4 text-tx-muted hover:text-tx transition-colors"
        >
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        {/* Icon */}
        <div className="text-4xl mb-4">{current.icon}</div>

        {/* Content */}
        <h2 className="text-lg font-bold text-tx mb-2">{current.title}</h2>
        <p className="text-sm text-tx-muted mb-6 leading-relaxed">{current.desc}</p>

        {/* Progress */}
        <div className="flex items-center gap-1 mb-6">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={clsx(
                "h-1.5 flex-1 rounded-full transition-all",
                i <= step ? "bg-brand-blue" : "bg-border"
              )}
            />
          ))}
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={handleComplete}
            className="flex-1 px-3 py-2 rounded-lg text-xs font-semibold text-tx-muted border border-border hover:border-border-light transition-colors"
          >
            Skip
          </button>
          <button
            onClick={handleNext}
            className="flex-1 px-3 py-2 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-blue-500 transition-colors"
          >
            {step === STEPS.length - 1 ? "Get Started" : "Next"}
          </button>
        </div>

        {/* Counter */}
        <div className="text-[10px] text-tx-dim text-center mt-3">
          {step + 1} / {STEPS.length}
        </div>
      </div>
    </div>
  );
}
