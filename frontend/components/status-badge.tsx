import type { ReactNode } from "react";

import { cn } from "@/lib/utils";


type StatusTone = "default" | "success" | "warning" | "danger" | "muted";

interface StatusBadgeProps {
  children: ReactNode;
  tone?: StatusTone;
}


const toneMap: Record<StatusTone, string> = {
  default: "border-line bg-white text-ink",
  success: "border-ok/20 bg-okSoft text-ok",
  warning: "border-warn/20 bg-warnSoft text-warn",
  danger: "border-danger/20 bg-dangerSoft text-danger",
  muted: "border-line bg-panel text-muted",
};


export function StatusBadge({ children, tone = "default" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.14em]",
        toneMap[tone],
      )}
    >
      {children}
    </span>
  );
}
