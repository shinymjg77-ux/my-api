import { StatusBadge } from "@/components/status-badge";
import type { HostMetricStatus } from "@/lib/types";
import { cn } from "@/lib/utils";


interface DonutMetricCardProps {
  label: string;
  usagePercent: number | null;
  status: HostMetricStatus;
  primaryValue: string;
  secondaryText: string;
  footnote: string;
}


const DONUT_SIZE = 124;
const DONUT_STROKE = 10;
const DONUT_RADIUS = (DONUT_SIZE - DONUT_STROKE) / 2;
const DONUT_CIRCUMFERENCE = 2 * Math.PI * DONUT_RADIUS;


function toneForMetricStatus(status: HostMetricStatus) {
  if (status === "critical") {
    return "danger";
  }
  if (status === "warning") {
    return "warning";
  }
  if (status === "unavailable") {
    return "muted";
  }
  return "success";
}


function chartColors(status: HostMetricStatus) {
  if (status === "critical") {
    return { stroke: "var(--danger)", track: "rgba(180, 35, 24, 0.12)" };
  }
  if (status === "warning") {
    return { stroke: "var(--warn)", track: "rgba(180, 83, 9, 0.12)" };
  }
  if (status === "unavailable") {
    return { stroke: "var(--line)", track: "rgba(90, 100, 112, 0.08)" };
  }
  return { stroke: "var(--ok)", track: "rgba(15, 118, 110, 0.12)" };
}


export function DonutMetricCard({
  label,
  usagePercent,
  status,
  primaryValue,
  secondaryText,
  footnote,
}: DonutMetricCardProps) {
  const normalizedPercent = usagePercent === null ? 0 : Math.min(Math.max(usagePercent, 0), 100);
  const progressOffset = DONUT_CIRCUMFERENCE - (normalizedPercent / 100) * DONUT_CIRCUMFERENCE;
  const colors = chartColors(status);

  return (
    <div className="panel-strong flex h-full flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">{label}</p>
        <StatusBadge tone={toneForMetricStatus(status)}>{status}</StatusBadge>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <div className="relative flex items-center justify-center">
          <svg
            aria-hidden="true"
            className="-rotate-90 overflow-visible"
            height={DONUT_SIZE}
            viewBox={`0 0 ${DONUT_SIZE} ${DONUT_SIZE}`}
            width={DONUT_SIZE}
          >
            <circle
              cx={DONUT_SIZE / 2}
              cy={DONUT_SIZE / 2}
              fill="none"
              r={DONUT_RADIUS}
              stroke={colors.track}
              strokeWidth={DONUT_STROKE}
            />
            <circle
              cx={DONUT_SIZE / 2}
              cy={DONUT_SIZE / 2}
              fill="none"
              r={DONUT_RADIUS}
              stroke={colors.stroke}
              strokeDasharray={DONUT_CIRCUMFERENCE}
              strokeDashoffset={progressOffset}
              strokeLinecap="round"
              strokeWidth={DONUT_STROKE}
            />
          </svg>

          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">Usage</span>
            <span
              className={cn(
                "mt-1 font-mono text-[1.7rem] font-semibold tracking-tight text-ink",
                status === "unavailable" && "text-muted",
              )}
            >
              {primaryValue}
            </span>
          </div>
        </div>

        <div className="space-y-1.5 text-center">
          <p className="text-sm font-semibold text-ink">{secondaryText}</p>
          <p className="text-xs leading-5 text-muted">{footnote}</p>
        </div>
      </div>
    </div>
  );
}
