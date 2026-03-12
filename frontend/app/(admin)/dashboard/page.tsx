import Link from "next/link";

import { DashboardRefreshControls } from "@/components/dashboard-refresh-controls";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { SummaryCard } from "@/components/summary-card";
import { formatBytes, formatCount, formatDateTime, formatDuration, formatPercent, formatStatusCode } from "@/lib/format";
import { getDashboardSummary, getOpsDashboard } from "@/lib/server-api";
import type { HostMetricStatus, OpsProcessAttentionLevel, OpsProcessStatus } from "@/lib/types";
import { cn } from "@/lib/utils";


function toneForOverall(status: "healthy" | "warning" | "critical") {
  if (status === "healthy") {
    return "success";
  }
  if (status === "critical") {
    return "danger";
  }
  return "warning";
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


export default async function DashboardPage() {
  const [summary, overview] = await Promise.all([getDashboardSummary(), getOpsDashboard()]);
  const pm2Groups = groupPm2Processes(overview.pm2_processes);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Dashboard"
        title="서버 운영 상태"
        description="systemd 서비스와 PM2 봇 프로세스를 함께 추적합니다. 읽기 전용으로 현재 살아 있는지, 불안정한지, 최근에 다시 뜬 흔적이 있는지 한 번에 확인합니다."
        action={
          <DashboardRefreshControls generatedAt={overview.generated_at} />
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Overall Status"
          value={overview.overall_status.toUpperCase()}
          hint="systemd 핵심 서비스와 PM2 프로세스를 합친 전체 상태"
          accent={<StatusBadge tone={toneForOverall(overview.overall_status)}>{overview.overall_status}</StatusBadge>}
        />
        <SummaryCard
          label="Systemd Healthy"
          value={`${formatCount(overview.summary.systemd_healthy)} / ${formatCount(overview.summary.systemd_total)}`}
          hint="현재 추적 중인 핵심 서비스의 정상 개수"
        />
        <SummaryCard
          label="PM2 Online"
          value={`${formatCount(overview.summary.pm2_online)} / ${formatCount(overview.summary.pm2_total)}`}
          hint="자동 발견된 PM2 프로세스 중 online 상태 개수"
          accent={<StatusBadge tone="success">bots</StatusBadge>}
        />
        <SummaryCard
          label="PM2 Unhealthy"
          value={formatCount(overview.summary.pm2_unhealthy)}
          hint="offline, stopped, errored 등 주의가 필요한 프로세스 수"
          accent={<StatusBadge tone={overview.summary.pm2_unhealthy > 0 ? "danger" : "muted"}>watch</StatusBadge>}
        />
      </section>

      <SectionCard title="서버 리소스" description="호스트 전체 CPU, 메모리, 루트 볼륨 사용량을 20초 단위로 새로 읽어옵니다.">
        <div className="grid gap-4 lg:grid-cols-3">
          <SummaryCard
            label="Host CPU"
            value={formatPercent(overview.host_metrics.cpu.usage_percent)}
            hint={
              overview.host_metrics.cpu.status === "unavailable"
                ? "현재 CPU 사용률을 읽지 못했습니다."
                : "서버 전체 CPU 사용률"
            }
            accent={<StatusBadge tone={toneForMetricStatus(overview.host_metrics.cpu.status)}>{overview.host_metrics.cpu.status}</StatusBadge>}
          />
          <SummaryCard
            label="Host Memory"
            value={
              overview.host_metrics.memory.used_bytes === null || overview.host_metrics.memory.total_bytes === null
                ? "-"
                : `${formatBytes(overview.host_metrics.memory.used_bytes)} / ${formatBytes(overview.host_metrics.memory.total_bytes)}`
            }
            hint={
              overview.host_metrics.memory.status === "unavailable"
                ? "현재 메모리 사용량을 읽지 못했습니다."
                : `가용 ${formatBytes(overview.host_metrics.memory.available_bytes)} · 사용률 ${formatPercent(overview.host_metrics.memory.usage_percent)}`
            }
            accent={<StatusBadge tone={toneForMetricStatus(overview.host_metrics.memory.status)}>{overview.host_metrics.memory.status}</StatusBadge>}
          />
          <SummaryCard
            label="Root Disk"
            value={
              overview.host_metrics.disk.used_bytes === null || overview.host_metrics.disk.total_bytes === null
                ? "-"
                : `${formatBytes(overview.host_metrics.disk.used_bytes)} / ${formatBytes(overview.host_metrics.disk.total_bytes)}`
            }
            hint={
              overview.host_metrics.disk.status === "unavailable"
                ? "루트 볼륨 사용량을 읽지 못했습니다."
                : `${overview.host_metrics.disk.mount_path} · 여유 ${formatBytes(overview.host_metrics.disk.free_bytes)} · 사용률 ${formatPercent(overview.host_metrics.disk.usage_percent)}`
            }
            accent={<StatusBadge tone={toneForMetricStatus(overview.host_metrics.disk.status)}>{overview.host_metrics.disk.status}</StatusBadge>}
          />
        </div>
      </SectionCard>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <SectionCard
          title="systemd 서비스"
          description="앱 자체와 프록시 같은 핵심 서비스 상태를 추적합니다."
        >
          {overview.systemd_services.length === 0 ? (
            <EmptyState title="추적 중인 systemd 서비스가 없습니다." description="OPS_SYSTEMD_UNITS 설정을 확인하세요." />
          ) : (
            <div className="space-y-3">
              {overview.systemd_services.map((service) => (
                <div key={service.name} className="rounded-2xl border border-line bg-panelStrong p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-ink">{service.name}</p>
                        <StatusBadge tone={service.is_healthy ? "success" : "danger"}>
                          {service.is_healthy ? "healthy" : "degraded"}
                        </StatusBadge>
                      </div>
                      <p className="text-sm leading-6 text-muted">{service.description || "설명 없음"}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <StatusBadge tone={service.active_state === "active" ? "success" : "danger"}>
                        {service.active_state}
                      </StatusBadge>
                      <StatusBadge tone="muted">{service.sub_state}</StatusBadge>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="PM2 봇 / 워커" description="자동 발견된 PM2 프로세스를 그룹별로 정리하고, 다운되었거나 재시작 이력이 있는 항목을 먼저 보여줍니다.">
          {overview.pm2_processes.length === 0 ? (
            <EmptyState
              title="자동 발견된 PM2 프로세스가 없습니다."
              description="PM2가 설치되지 않았거나 현재 관리 중인 프로세스가 없습니다."
            />
          ) : (
            <div className="space-y-3">
              {pm2Groups.map((group) => (
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
          )}
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <SectionCard title="수집 경고" description="상태 수집 중 일부 실패가 있었거나 확인이 필요한 조건입니다.">
          {overview.warnings.length === 0 ? (
            <EmptyState title="현재 수집 경고가 없습니다." description="PM2와 systemd 조회가 정상적으로 완료됐습니다." />
          ) : (
            <div className="space-y-3">
              {overview.warnings.map((warning) => (
                <div key={warning} className="rounded-2xl border border-warn/20 bg-warnSoft p-4 text-sm text-warn">
                  {warning}
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="주의가 필요한 최근 로그" description="실패 또는 경고 성격의 최근 이벤트를 우선 노출합니다.">
          {summary.recent_error_logs.length === 0 ? (
            <EmptyState title="최근 에러 로그가 없습니다." description="현재까지 실패 로그가 없어 비교적 안정적인 상태입니다." />
          ) : (
            <div className="space-y-3">
              {summary.recent_error_logs.map((log) => (
                <div key={log.id} className="rounded-2xl border border-line bg-panelStrong p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge tone={log.is_success ? "success" : "danger"}>
                      {log.is_success ? "Success" : "Failure"}
                    </StatusBadge>
                    <StatusBadge tone={log.level === "error" ? "danger" : log.level === "warning" ? "warning" : "muted"}>
                      {log.level}
                    </StatusBadge>
                    <StatusBadge>{log.log_type}</StatusBadge>
                  </div>
                  <p className="mt-3 text-sm font-semibold text-ink">{log.message}</p>
                  <div className="mt-2 grid gap-2 text-xs text-muted sm:grid-cols-2">
                    <span>API: {log.api_name || "-"}</span>
                    <span>DB: {log.db_connection_name || "-"}</span>
                    <span>Status: {formatStatusCode(log.status_code)}</span>
                    <span>시각: {formatDateTime(log.created_at)}</span>
                  </div>
                  {log.detail ? <p className="mt-2 text-sm leading-6 text-muted">{log.detail}</p> : null}
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      <SectionCard title="보조 도구" description="기존 관리 화면은 보조 도구로 유지합니다.">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Link className="panel-strong block p-5 transition hover:border-ink" href="/logs">
            <p className="text-sm font-semibold text-ink">로그 검색</p>
            <p className="mt-2 text-sm leading-6 text-muted">인증 실패, 운영 이벤트, 에러 이력을 추적합니다.</p>
          </Link>
          <Link className="panel-strong block p-5 transition hover:border-ink" href="/settings">
            <p className="text-sm font-semibold text-ink">보안 / 설정</p>
            <p className="mt-2 text-sm leading-6 text-muted">관리자 비밀번호와 운영 자동화 메모를 확인합니다.</p>
          </Link>
          <Link className="panel-strong block p-5 transition hover:border-ink" href="/apis">
            <p className="text-sm font-semibold text-ink">API 관리</p>
            <p className="mt-2 text-sm leading-6 text-muted">기존 API 레지스트리 화면은 그대로 접근할 수 있습니다.</p>
          </Link>
          <Link className="panel-strong block p-5 transition hover:border-ink" href="/db-connections">
            <p className="text-sm font-semibold text-ink">DB 연결 관리</p>
            <p className="mt-2 text-sm leading-6 text-muted">DB 연결 정보 저장과 즉시 테스트를 계속 지원합니다.</p>
          </Link>
        </div>
      </SectionCard>
    </div>
  );
}
