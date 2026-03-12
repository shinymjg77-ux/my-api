import Link from "next/link";

import { DashboardRefreshControls } from "@/components/dashboard-refresh-controls";
import { DonutMetricCard } from "@/components/donut-metric-card";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { formatBytes, formatCount, formatPercent } from "@/lib/format";
import { getOpsDashboard } from "@/lib/server-api";


function toneForOverall(status: "healthy" | "warning" | "critical") {
  if (status === "healthy") {
    return "success";
  }
  if (status === "critical") {
    return "danger";
  }
  return "warning";
}


export default async function DashboardPage() {
  const overview = await getOpsDashboard();
  const quickStats = [
    {
      label: "Systemd",
      value: `${formatCount(overview.summary.systemd_healthy)} / ${formatCount(overview.summary.systemd_total)}`,
      hint: "핵심 서비스 정상",
      tone: overview.summary.systemd_healthy === overview.summary.systemd_total ? "success" : "warning",
      badge: overview.summary.systemd_total === 0 ? "none" : `${formatCount(overview.summary.systemd_total)} tracked`,
    },
    {
      label: "PM2 Online",
      value: `${formatCount(overview.summary.pm2_online)} / ${formatCount(overview.summary.pm2_total)}`,
      hint: "온라인 프로세스",
      tone: overview.summary.pm2_online === overview.summary.pm2_total ? "success" : "warning",
      badge: `${formatCount(overview.summary.pm2_total)} bots`,
    },
    {
      label: "PM2 Watch",
      value: formatCount(overview.summary.pm2_unhealthy),
      hint: "주의 프로세스",
      tone: overview.summary.pm2_unhealthy > 0 ? "danger" : "muted",
      badge: overview.summary.pm2_unhealthy > 0 ? "action" : "clear",
    },
  ] as const;

  const quickMeta = [
    { label: "Tracked Services", value: formatCount(overview.summary.systemd_total) },
    { label: "Tracked PM2", value: formatCount(overview.summary.pm2_total) },
    { label: "Warnings", value: formatCount(overview.warnings.length) },
    { label: "Refresh", value: "20s" },
  ] as const;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Dashboard"
        title="서버 운영 상태"
        description="핵심 서비스와 봇 상태를 한 번에 스캔하는 개요 화면입니다. 상세 상태와 런타임 로그는 별도 화면에서 확인합니다."
        action={
          <DashboardRefreshControls generatedAt={overview.generated_at} />
        }
      />

      <SectionCard title="서버 리소스" description="호스트 전체 CPU, 메모리, 루트 볼륨 사용량을 20초 단위로 새로 읽어옵니다.">
        <div className="grid gap-4 lg:grid-cols-3">
          <DonutMetricCard
            label="Host CPU"
            primaryValue={formatPercent(overview.host_metrics.cpu.usage_percent)}
            secondaryText="서버 전체 CPU 사용률"
            footnote={
              overview.host_metrics.cpu.status === "unavailable"
                ? "현재 CPU 사용률을 읽지 못했습니다."
                : "20초마다 갱신되는 호스트 스냅샷"
            }
            status={overview.host_metrics.cpu.status}
            usagePercent={overview.host_metrics.cpu.usage_percent}
          />
          <DonutMetricCard
            label="Host Memory"
            primaryValue={formatPercent(overview.host_metrics.memory.usage_percent)}
            secondaryText={
              overview.host_metrics.memory.used_bytes === null || overview.host_metrics.memory.total_bytes === null
                ? "-"
                : `${formatBytes(overview.host_metrics.memory.used_bytes)} / ${formatBytes(overview.host_metrics.memory.total_bytes)}`
            }
            footnote={
              overview.host_metrics.memory.status === "unavailable"
                ? "현재 메모리 사용량을 읽지 못했습니다."
                : `가용 ${formatBytes(overview.host_metrics.memory.available_bytes)}`
            }
            status={overview.host_metrics.memory.status}
            usagePercent={overview.host_metrics.memory.usage_percent}
          />
          <DonutMetricCard
            label="Root Disk"
            primaryValue={formatPercent(overview.host_metrics.disk.usage_percent)}
            secondaryText={
              overview.host_metrics.disk.used_bytes === null || overview.host_metrics.disk.total_bytes === null
                ? "-"
                : `${formatBytes(overview.host_metrics.disk.used_bytes)} / ${formatBytes(overview.host_metrics.disk.total_bytes)}`
            }
            footnote={
              overview.host_metrics.disk.status === "unavailable"
                ? "루트 볼륨 사용량을 읽지 못했습니다."
                : `${overview.host_metrics.disk.mount_path} · 여유 ${formatBytes(overview.host_metrics.disk.free_bytes)}`
            }
            status={overview.host_metrics.disk.status}
            usagePercent={overview.host_metrics.disk.usage_percent}
          />
        </div>
      </SectionCard>

      <SectionCard title="운영 개요" description="첫 화면에서는 지금 위험한지와 추적 범위만 압축해서 보여줍니다.">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,2fr)]">
          <div className="panel-strong flex h-full flex-col justify-between gap-4 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Overall Status</p>
                <p className="font-mono text-[2rem] font-semibold tracking-tight text-ink">
                  {overview.overall_status.toUpperCase()}
                </p>
                <p className="text-sm leading-6 text-muted">systemd 핵심 서비스와 PM2 프로세스를 합친 현재 운영 상태</p>
              </div>
              <StatusBadge tone={toneForOverall(overview.overall_status)}>{overview.overall_status}</StatusBadge>
            </div>

            <div className="flex flex-wrap gap-2">
              {quickMeta.map((item) => (
                <div
                  key={item.label}
                  className="rounded-full border border-line bg-panel px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted"
                >
                  {item.label} {item.value}
                </div>
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {quickStats.map((item) => (
              <div key={item.label} className="panel-strong flex h-full flex-col gap-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">{item.label}</p>
                  <StatusBadge tone={item.tone}>{item.badge}</StatusBadge>
                </div>
                <p className="font-mono text-2xl font-semibold tracking-tight text-ink">{item.value}</p>
                <p className="text-sm text-muted">{item.hint}</p>
              </div>
            ))}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="빠른 이동" description="상세 런타임과 운영 도구는 전용 화면으로 분리했습니다.">
        <div className="grid gap-4 md:grid-cols-3">
          <Link className="panel-strong block p-5 transition hover:border-ink" href="/runtime">
            <p className="text-sm font-semibold text-ink">런타임 상세</p>
            <p className="mt-2 text-sm leading-6 text-muted">systemd, PM2, 최근 런타임 로그를 자세히 확인합니다.</p>
          </Link>
          <Link className="panel-strong block p-5 transition hover:border-ink" href="/logs">
            <p className="text-sm font-semibold text-ink">이벤트 로그</p>
            <p className="mt-2 text-sm leading-6 text-muted">인증 실패, 운영 이벤트, 에러 이력을 검색합니다.</p>
          </Link>
          <Link className="panel-strong block p-5 transition hover:border-ink" href="/settings">
            <p className="text-sm font-semibold text-ink">보안 / 설정</p>
            <p className="mt-2 text-sm leading-6 text-muted">관리자 보안과 운영 자동화 설정 상태를 확인합니다.</p>
          </Link>
        </div>
      </SectionCard>

      {overview.warnings.length > 0 ? (
        <SectionCard title="수집 경고" description="현재 개요 수집 중 확인이 필요한 조건입니다.">
          <div className="space-y-3">
            {overview.warnings.map((warning) => (
              <div key={warning} className="rounded-2xl border border-warn/20 bg-warnSoft p-4 text-sm text-warn">
                {warning}
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}
