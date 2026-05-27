export default function LoadingSkeleton({ type = "card", className = "" }) {
  if (type === "card") {
    return (
      <div className={`bg-bg-card border border-border rounded-xl p-4 animate-pulse ${className}`}>
        <div className="h-4 bg-border rounded w-1/3 mb-3"></div>
        <div className="space-y-2">
          <div className="h-3 bg-border rounded"></div>
          <div className="h-3 bg-border rounded w-5/6"></div>
        </div>
      </div>
    );
  }

  if (type === "chart") {
    return (
      <div className={`bg-bg-card border border-border rounded-xl p-4 animate-pulse ${className}`}>
        <div className="h-64 bg-border rounded"></div>
      </div>
    );
  }

  if (type === "table") {
    return (
      <div className={`space-y-2 ${className}`}>
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-10 bg-bg-card border border-border rounded animate-pulse"></div>
        ))}
      </div>
    );
  }

  return <div className={`h-20 bg-bg-card border border-border rounded animate-pulse ${className}`}></div>;
}
