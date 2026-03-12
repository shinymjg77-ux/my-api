import type { ReactNode } from "react";


interface SummaryCardProps {
  label: string;
  value: string;
  hint: string;
  accent?: ReactNode;
}


export function SummaryCard({ label, value, hint, accent }: SummaryCardProps) {
  return (
    <div className="panel-strong p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">{label}</p>
        {accent}
      </div>
      <p className="metric-value mt-4">{value}</p>
      <p className="mt-3 text-sm text-muted">{hint}</p>
    </div>
  );
}
