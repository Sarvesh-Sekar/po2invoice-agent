import { cn } from "@/lib/utils";

export interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return <div className={cn("animate-pulse rounded-md bg-gray-200", className)} />;
}

export function SkeletonRow({ cols = 5 }: { cols?: number }) {
  return (
    <div className="flex w-full items-center gap-4 border-b border-gray-100 px-4 py-3">
      {Array.from({ length: cols }).map((_, index) => (
        <Skeleton key={index} className={cn("h-4", index === 0 ? "w-24" : "flex-1")} />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      <div className={cn("flex items-center gap-4 border-b border-gray-200 bg-gray-50 px-4 py-3")}>
        {Array.from({ length: cols }).map((_, index) => (
          <Skeleton key={index} className={cn("h-3.5", index === 0 ? "w-24" : "flex-1")} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, index) => (
        <SkeletonRow key={index} cols={cols} />
      ))}
    </div>
  );
}