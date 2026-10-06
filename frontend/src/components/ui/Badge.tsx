import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type BadgeTone =
  | "gray"
  | "blue"
  | "green"
  | "amber"
  | "red"
  | "indigo"
  | "purple";

export interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}

const toneClasses: Record<BadgeTone, string> = {
  gray: "bg-gray-100 text-gray-700 ring-gray-500/15",
  blue: "bg-blue-50 text-blue-700 ring-blue-600/15",
  green: "bg-green-50 text-green-700 ring-green-600/15",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  red: "bg-red-50 text-red-700 ring-red-600/15",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-600/15",
  purple: "bg-purple-50 text-purple-700 ring-purple-600/15",
};

export function Badge({ tone = "gray", children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        toneClasses[tone],
        className
      )}
    >
      {children}
    </span>
  );
}