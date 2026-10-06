import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";

export interface CardSectionProps {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function SectionCard({ title, action, children, className }: CardSectionProps) {
  return (
    <div className={`rounded-lg border border-gray-200 bg-white ${className ?? ""}`}>
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export interface ListCardProps<T> {
  title: string;
  viewAllTo?: string;
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  onRetry?: () => void;
  items: T[] | undefined;
  emptyTitle: string;
  emptyDescription?: string;
  getKey: (item: T) => string;
  renderItem: (item: T) => ReactNode;
}

export function ListCard<T>({
  title,
  viewAllTo,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  items,
  emptyTitle,
  emptyDescription,
  getKey,
  renderItem,
}: ListCardProps<T>) {
  return (
    <SectionCard
      title={title}
      action={
        viewAllTo ? (
          <Link to={viewAllTo} className="text-xs font-medium text-indigo-600 hover:text-indigo-700">
            View all
          </Link>
        ) : undefined
      }
    >
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="h-9 w-9 rounded-full" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3.5 w-32" />
                <Skeleton className="h-3 w-20" />
              </div>
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <ErrorState message={errorMessage ?? `Unable to load ${title.toLowerCase()}.`} onRetry={onRetry} />
      ) : !items || items.length === 0 ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <ul className="divide-y divide-gray-100">
          {items.map((item) => (
            <li key={getKey(item)} className="py-2.5 first:pt-0 last:pb-0">
              {renderItem(item)}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}