import Link from "next/link";

import { DashboardRefreshControls } from "@/components/dashboard-refresh-controls";
import { EmptyState } from "@/components/empty-state";
import { OpsPm2Groups } from "@/components/ops-pm2-groups";
import { OpsSystemdServiceList } from "@/components/ops-systemd-service-list";
import { PageHeader } from "@/components/page-header";
import { RuntimeLogSourceCard } from "@/components/runtime-log-source-card";
import { SectionCard } from "@/components/section-card";
import { getOpsDashboard, getRuntimeLogs } from "@/lib/server-api";


export default async function RuntimePage() {
  const [overview, runtimeLogs] = await Promise.all([getOpsDashboard(), getRuntimeLogs()]);
  const runtimeWarnings = Array.from(new Set([...overview.warnings, ...runtimeLogs.warnings]));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Runtime"
        title="런타임 상세"
        description="systemd 서비스, PM2 프로세스, 최근 런타임 로그를 상세하게 확인하는 화면입니다."
        action={<DashboardRefreshControls generatedAt={runtimeLogs.generated_at} />}
      />

      <div className="flex flex-wrap gap-3">
        <Link className="button-secondary" href="/dashboard">
          개요로 돌아가기
        </Link>
        <Link className="button-secondary" href="/logs">
          이벤트 로그 보기
        </Link>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <SectionCard title="systemd 서비스" description="앱 자체와 프록시 같은 핵심 서비스 상태를 상세하게 추적합니다.">
          <OpsSystemdServiceList services={overview.systemd_services} />
        </SectionCard>

        <SectionCard title="PM2 봇 / 워커" description="자동 발견된 PM2 프로세스를 그룹별로 정리하고, 불안정한 항목을 먼저 보여줍니다.">
          <OpsPm2Groups processes={overview.pm2_processes} />
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <SectionCard title="systemd 최근 로그" description="핵심 서비스별 최근 30줄을 읽기 전용으로 보여줍니다.">
          {runtimeLogs.systemd_logs.length === 0 ? (
            <EmptyState title="표시할 systemd 로그가 없습니다." description="추적 중인 서비스가 없거나 현재 로그를 읽을 수 없습니다." />
          ) : (
            <div className="space-y-3">
              {runtimeLogs.systemd_logs.map((source) => (
                <RuntimeLogSourceCard key={`${source.source_type}-${source.source_name}`} source={source} />
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="PM2 최근 로그" description="자동 발견된 PM2 프로세스별 최근 30줄을 읽기 전용으로 보여줍니다.">
          {runtimeLogs.pm2_logs.length === 0 ? (
            <EmptyState title="표시할 PM2 로그가 없습니다." description="관리 중인 PM2 프로세스가 없거나 현재 로그를 읽을 수 없습니다." />
          ) : (
            <div className="space-y-3">
              {runtimeLogs.pm2_logs.map((source) => (
                <RuntimeLogSourceCard key={`${source.source_type}-${source.source_name}`} source={source} />
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      {runtimeWarnings.length > 0 ? (
        <SectionCard title="수집 경고" description="런타임 상세 수집 중 일부 실패가 있었거나 확인이 필요한 조건입니다.">
          <div className="space-y-3">
            {runtimeWarnings.map((warning) => (
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
