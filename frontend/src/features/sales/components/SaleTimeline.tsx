import { Button } from "@/components/ui/Button";
import { SALE_STATUSES } from "@/constants";
import { cn, titleCase } from "@/lib/utils";
import type { SaleStatus } from "@/types/common";

export type SaleTimelineStatus = SaleStatus;

export interface SaleTimelineProps {
  status: SaleStatus;
  onAdvance?: () => void;
  advancing?: boolean;
  allowAdvance?: boolean;
}

export function SaleTimeline({ status, onAdvance, advancing = false, allowAdvance = true }: SaleTimelineProps) {
  const currentIndex = SALE_STATUSES.indexOf(status);
  const nextStatus: SaleStatus | null =
    currentIndex >= 0 && currentIndex < SALE_STATUSES.length - 1 ? SALE_STATUSES[currentIndex + 1] : null;

  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold text-gray-900">Sale Timeline</h2>
      <p className="mb-3 text-xs text-gray-500">
        Status advances sequentially from Created to Delivered. Notify the backend for each transition; it
        orchestrates the invoice workflow automatically once a sale is delivered.
      </p>
      <ol className="flex items-center">
        {SALE_STATUSES.map((step, index) => {
          const complete = index < currentIndex;
          const current = index === currentIndex;
          return (
            <li key={step} className="flex flex-1 items-center last:flex-none">
              <div className="flex flex-col items-center gap-1.5">
                <span
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold",
                    complete && "bg-green-500 text-white",
                    current && "bg-indigo-600 text-white ring-4 ring-indigo-100",
                    !complete && !current && "bg-gray-200 text-gray-500"
                  )}
                >
                  {complete ? "✓" : index + 1}
                </span>
                <span
                  className={cn(
                    "text-xs font-medium",
                    current ? "text-indigo-700" : complete ? "text-green-700" : "text-gray-400"
                  )}
                >
                  {titleCase(step)}
                </span>
              </div>
              {index < SALE_STATUSES.length - 1 && (
                <div
                  className={cn(
                    "mx-2 h-0.5 flex-1",
                    index < currentIndex ? "bg-green-400" : "bg-gray-200"
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>

      {nextStatus && allowAdvance && onAdvance && (
        <div className="mt-4 flex justify-end">
          <Button variant="secondary" size="sm" loading={advancing} onClick={onAdvance}>
            Mark as {titleCase(nextStatus)}
          </Button>
        </div>
      )}
    </div>
  );
}