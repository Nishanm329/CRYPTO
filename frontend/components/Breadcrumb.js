import clsx from "clsx";

export default function Breadcrumb({ items }) {
  // items: [{ label, onClick }, ...]
  return (
    <div className="flex items-center gap-2 text-xs text-tx-muted px-4 py-2 border-b border-border/40 bg-bg/40">
      {items.map((item, idx) => (
        <div key={idx} className="flex items-center gap-2">
          {idx > 0 && <span className="text-tx-dim">/</span>}
          <button
            onClick={item.onClick}
            className={clsx(
              "transition-colors",
              item.active
                ? "text-brand-blue font-semibold"
                : "text-tx-muted hover:text-tx"
            )}
          >
            {item.label}
          </button>
        </div>
      ))}
    </div>
  );
}
