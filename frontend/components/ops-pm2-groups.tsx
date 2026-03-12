import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { formatBytes, formatCount, formatDuration, formatPercent } from "@/lib/format";
import type { OpsProcessAttentionLevel, OpsProcessStatus } from "@/lib/types";
import { cn } from "@/lib/utils";


interface OpsPm2GroupsProps {
  processes: OpsProcessStatus[];
}


function toneForAttention(level: OpsProcessAttentionLevel) {
  if (level === "critical") {
    return "danger";
  }
  if (level === "warning") {
    return "warning";
  }
  return "success";
}


function processCardClass(level: OpsProcessAttentionLevel) {
  return cn(
    "rounded-2xl border p-4",
    level === "critical" && "border-danger/30 bg-dangerSoft/40",
    level === "warning" && "border-warn/25 bg-warnSoft/40",
    level === "healthy" && "border-line bg-panelStrong",
  );
}


function groupPm2Processes(processes: OpsProcessStatus[]) {
  const groups = new Map<
    string,
    {
      key: string;
      label: string;
      processes: OpsProcessStatus[];
      criticalCount: number;
      warningCount: number;
    }
  >();

  for (const process of processes) {
    const existingGroup = groups.get(process.group_key);
    if (existingGroup) {
      existingGroup.processes.push(process);
      if (process.attention_level === "critical") {
        existingGroup.criticalCount += 1;
      } else if (process.attention_level === "warning") {
        existingGroup.warningCount += 1;
      }
      continue;
    }

    groups.set(process.group_key, {
      key: process.group_key,
      label: process.group_label,
      processes: [process],
      criticalCount: process.attention_level === "critical" ? 1 : 0,
      warningCount: process.attention_level === "warning" ? 1 : 0,
    });
  }

  return Array.from(groups.values());
}


export function OpsPm2Groups({ processes }: OpsPm2GroupsProps) {
  const groups = groupPm2Processes(processes);

  if (groups.length === 0) {
    return (
      <EmptyState
        title="자동 발견된 PM2 프로세스가 없습니다."
        description="PM2가 설치되지 않았거나 현재 관리 중인 프로세스가 없습니다."
      />
    );
  }

  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <div key={group.key} className="space-y-3 rounded-[1.6rem] border border-line/80 bg-panel p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">Process Group</p>
              <h3 className="text-sm font-semibold text-ink">{group.label}</h3>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge tone="muted">{formatCount(group.processes.length)} procs</StatusBadge>
              {group.criticalCount > 0 ? (
                <StatusBadge tone="danger">{formatCount(group.criticalCount)} unhealthy</StatusBadge>
              ) : null}
              {group.warningCount > 0 ? (
                <StatusBadge tone="warning">{formatCount(group.warningCount)} restart watch</StatusBadge>
              ) : null}
            </div>
          </div>

          {group.processes.map((process) => (
            <div key={process.name} className={processCardClass(process.attention_level)}>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-ink">{process.name}</p>
                    <StatusBadge tone={toneForAttention(process.attention_level)}>{process.status}</StatusBadge>
                    {process.attention_level === "warning" ? (
                      <StatusBadge tone="warning">재시작 주의</StatusBadge>
                    ) : null}
                    <StatusBadge tone="muted">pid {process.pid ?? "-"}</StatusBadge>
                  </div>
                  <p className="break-all text-sm text-muted">{process.cwd || "작업 디렉터리 정보 없음"}</p>
                </div>
                <div className="grid gap-2 text-xs text-muted sm:grid-cols-2 lg:min-w-[280px]">
                  <span>재시작: {formatCount(process.restart_count)}</span>
                  <span>업타임: {formatDuration(process.uptime_seconds)}</span>
                  <span>CPU: {formatPercent(process.cpu_percent)}</span>
                  <span>메모리: {formatBytes(process.memory_bytes)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
