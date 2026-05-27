import { useState, useEffect } from "react";
import clsx from "clsx";

export default function Toast({ message, action, onAction, duration = 5000, type = "default" }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(false), duration);
    return () => clearTimeout(timer);
  }, [duration]);

  if (!visible) return null;

  const bgColor =
    type === "success" ? "bg-brand-green/10 border-brand-green/20" :
    type === "error" ? "bg-brand-red/10 border-brand-red/20" :
    "bg-bg-card border-border";

  const textColor =
    type === "success" ? "text-brand-green" :
    type === "error" ? "text-brand-red" :
    "text-tx";

  return (
    <div className={clsx(
      "fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96",
      "bg-bg-card border border-border rounded-lg p-4 shadow-lg",
      "flex items-center justify-between gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300"
    )}>
      <span className={clsx("text-sm font-medium flex-1", textColor)}>
        {message}
      </span>
      {action && (
        <button
          onClick={() => {
            onAction?.();
            setVisible(false);
          }}
          className="text-xs font-semibold text-brand-blue hover:text-blue-400 transition-colors whitespace-nowrap"
        >
          {action}
        </button>
      )}
      <button
        onClick={() => setVisible(false)}
        className="text-tx-muted hover:text-tx transition-colors flex-shrink-0"
      >
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}
