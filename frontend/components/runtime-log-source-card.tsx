import { StatusBadge } from "@/components/status-badge";
import type { RuntimeLogSource } from "@/lib/types";


interface RuntimeLogSourceCardProps {
  source: RuntimeLogSource;
}


function toneForStatus(status: RuntimeLogSource["status"]) {
  if (status === "unavailable") {
    return "warning";
  }
  return "success";
}


export function RuntimeLogSourceCard({ source }: RuntimeLogSourceCardProps) {
  return (
    <div className="rounded-2xl border border-line bg-panelStrong p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-ink">{source.source_name}</p>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">{source.source_type}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusBadge tone="muted">{source.lines.length} lines</StatusBadge>
          <StatusBadge tone={toneForStatus(source.status)}>{source.status}</StatusBadge>
        </div>
      </div>

      {source.lines.length === 0 ? (
        <div className="mt-4 rounded-2xl border border-line bg-panel px-4 py-5 text-sm text-muted">
          {source.status === "unavailable" ? "현재 로그를 읽지 못했습니다." : "최근 로그가 없습니다."}
        </div>
      ) : (
        <pre className="mt-4 max-h-[360px] overflow-auto rounded-2xl border border-line bg-white px-4 py-3 text-xs leading-6 text-ink">
          {source.lines.join("\n")}
        </pre>
      )}
    </div>
  );
}
