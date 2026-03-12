import Link from "next/link";

import { DashboardRefreshControls } from "@/components/dashboard-refresh-controls";
import { DonutMetricCard } from "@/components/donut-metric-card";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { SummaryCard } from "@/components/summary-card";
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

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Tracked Services"
          value={formatCount(overview.summary.systemd_total)}
          hint="핵심 systemd 서비스 추적 개수"
        />
        <SummaryCard
          label="Tracked PM2"
          value={formatCount(overview.summary.pm2_total)}
          hint="자동 발견된 PM2 프로세스 개수"
        />
        <SummaryCard
          label="Warnings"
          value={formatCount(overview.warnings.length)}
          hint="상태 수집 중 확인이 필요한 경고 개수"
          accent={<StatusBadge tone={overview.warnings.length > 0 ? "warning" : "muted"}>ops</StatusBadge>}
        />
        <SummaryCard
          label="Refresh"
          value="20s"
          hint="자동 갱신 주기"
          accent={<StatusBadge tone="muted">readonly</StatusBadge>}
        />
      </div>

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
