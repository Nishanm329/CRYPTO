import clsx from "clsx";

function Skeleton({ className = "h-4 w-full" }) {
  return (
    <div
      className={clsx(
        "bg-gradient-to-r from-border via-border/50 to-border animate-pulse rounded",
        className
      )}
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-4 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-6 w-32" />
      <Skeleton className="h-4 w-16" />
    </div>
  );
}

export function TableRowSkeleton({ columns = 4 }) {
  return (
    <tr className="border-b border-border/40">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="py-2 px-2">
          <Skeleton className="h-4" />
        </td>
      ))}
    </tr>
  );
}

export function ChartSkeleton() {
  return (
    <div className="w-full h-full bg-bg-card border border-border rounded-xl p-4 flex items-center justify-center">
      <div className="space-y-4 w-full">
        <Skeleton className="h-8 w-32" />
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-20 flex-1" />
          ))}
        </div>
        <Skeleton className="h-4 w-full" />
      </div>
    </div>
  );
}

export default Skeleton;
