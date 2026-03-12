import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { SummaryCard } from "@/components/summary-card";
import { formatCount, formatDateTime, formatStatusCode } from "@/lib/format";
import { getDashboardSummary } from "@/lib/server-api";


export default async function DashboardPage() {
  const summary = await getDashboardSummary();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Dashboard"
        title="운영 현황 개요"
        description="최근 성공/실패 흐름과 주의가 필요한 에러 로그를 한 번에 확인합니다."
        action={
          <div className="flex flex-wrap gap-2">
            <Link className="button-secondary" href="/apis">
              API 관리
            </Link>
            <Link className="button-primary" href="/db-connections">
              DB 연결 관리
            </Link>
          </div>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Tracked APIs" value={formatCount(summary.api_count)} hint="현재 관리 중인 API 엔드포인트 수" />
        <SummaryCard
          label="DB Connections"
          value={formatCount(summary.db_connection_count)}
          hint="저장된 데이터베이스 연결 구성 수"
        />
        <SummaryCard
          label="Recent Success"
          value={formatCount(summary.recent_success_count)}
          hint="최근 집계 구간의 API 성공 로그 수"
          accent={<StatusBadge tone="success">Healthy</StatusBadge>}
        />
        <SummaryCard
          label="Recent Failure"
          value={formatCount(summary.recent_failure_count)}
          hint="최근 집계 구간의 API 실패 로그 수"
          accent={<StatusBadge tone={summary.recent_failure_count > 0 ? "danger" : "muted"}>Attention</StatusBadge>}
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
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

        <SectionCard title="빠른 이동" description="운영 중 자주 쓰는 화면으로 바로 이동합니다.">
          <div className="grid gap-4">
            <Link className="panel-strong block p-5 transition hover:border-ink" href="/apis">
              <p className="text-sm font-semibold text-ink">API 엔드포인트 관리</p>
              <p className="mt-2 text-sm leading-6 text-muted">새 API 등록, 활성 상태 변경, 최근 수정 내역 확인</p>
            </Link>
            <Link className="panel-strong block p-5 transition hover:border-ink" href="/db-connections">
              <p className="text-sm font-semibold text-ink">DB 연결 관리</p>
              <p className="mt-2 text-sm leading-6 text-muted">연결 정보 저장, 암호 갱신, 즉시 테스트 수행</p>
            </Link>
            <Link className="panel-strong block p-5 transition hover:border-ink" href="/logs">
              <p className="text-sm font-semibold text-ink">로그 검색</p>
              <p className="mt-2 text-sm leading-6 text-muted">기간, API 이름, 성공 여부 기준으로 운영 로그 확인</p>
            </Link>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
