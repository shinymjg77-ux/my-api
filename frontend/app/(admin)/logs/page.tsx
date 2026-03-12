import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { formatDateTime, formatStatusCode } from "@/lib/format";
import { getLogs } from "@/lib/server-api";
import { cn } from "@/lib/utils";


function pick(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}


function buildPageHref(searchParams: Record<string, string | string[] | undefined>, page: number) {
  const urlSearchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(searchParams)) {
    const actual = pick(value);
    if (!actual || key === "page") {
      continue;
    }
    urlSearchParams.set(key, actual);
  }

  urlSearchParams.set("page", String(page));
  return `/logs?${urlSearchParams.toString()}`;
}


export default async function LogsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedSearchParams = await searchParams;
  const dateFrom = pick(resolvedSearchParams.date_from) ?? "";
  const dateTo = pick(resolvedSearchParams.date_to) ?? "";
  const apiName = pick(resolvedSearchParams.api_name) ?? "";
  const statusCode = pick(resolvedSearchParams.status_code) ?? "";
  const isSuccess = pick(resolvedSearchParams.is_success) ?? "";
  const currentPage = Number(pick(resolvedSearchParams.page) ?? "1") || 1;
  const pageSize = 20;

  const response = await getLogs({
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    api_name: apiName || undefined,
    status_code: statusCode || undefined,
    is_success: isSuccess || undefined,
    page: currentPage,
    page_size: pageSize,
  });

  const hasPrevPage = currentPage > 1;
  const hasNextPage = currentPage * pageSize < response.total;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Logs"
        title="운영 로그 조회"
        description="기간, API 이름, 상태 코드, 성공 여부로 필터링하여 최근 운영 이벤트를 추적합니다."
      />

      <SectionCard title="검색 필터" description="운영 중 자주 보는 필터만 우선 노출했습니다.">
        <form className="grid gap-4 md:grid-cols-2 xl:grid-cols-5" method="GET">
          <label className="field">
            <span className="label">시작일</span>
            <input className="input" type="date" name="date_from" defaultValue={dateFrom} />
          </label>

          <label className="field">
            <span className="label">종료일</span>
            <input className="input" type="date" name="date_to" defaultValue={dateTo} />
          </label>

          <label className="field">
            <span className="label">API 이름</span>
            <input className="input" name="api_name" defaultValue={apiName} placeholder="예: Billing" />
          </label>

          <label className="field">
            <span className="label">상태 코드</span>
            <input className="input" name="status_code" defaultValue={statusCode} placeholder="예: 500" />
          </label>

          <label className="field">
            <span className="label">성공 여부</span>
            <select className="select" name="is_success" defaultValue={isSuccess}>
              <option value="">전체</option>
              <option value="true">성공만</option>
              <option value="false">실패만</option>
            </select>
          </label>

          <div className="xl:col-span-5 flex flex-wrap gap-3">
            <button className="button-primary" type="submit">
              필터 적용
            </button>
            <Link className="button-secondary" href="/logs">
              초기화
            </Link>
          </div>
        </form>
      </SectionCard>

      <SectionCard
        title="이벤트 스트림"
        description={`총 ${response.total}건 중 현재 페이지 ${response.page}를 보고 있습니다.`}
      >
        {response.items.length === 0 ? (
          <EmptyState title="조건에 맞는 로그가 없습니다." description="필터를 완화하거나 다른 기간으로 다시 조회해 보세요." />
        ) : (
          <div className="space-y-5">
            <div className="table-shell overflow-x-auto">
              <table className="table min-w-[980px]">
                <thead>
                  <tr>
                    <th>시각</th>
                    <th>타입</th>
                    <th>상태</th>
                    <th>메시지</th>
                    <th>API / DB</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {response.items.map((item) => (
                    <tr key={item.id}>
                      <td className="whitespace-nowrap text-xs text-muted">{formatDateTime(item.created_at)}</td>
                      <td>
                        <div className="flex flex-wrap gap-2">
                          <StatusBadge>{item.log_type}</StatusBadge>
                          <StatusBadge tone={item.level === "error" ? "danger" : item.level === "warning" ? "warning" : "muted"}>
                            {item.level}
                          </StatusBadge>
                        </div>
                      </td>
                      <td>
                        <StatusBadge tone={item.is_success ? "success" : "danger"}>
                          {item.is_success ? "Success" : "Failure"}
                        </StatusBadge>
                      </td>
                      <td>
                        <div className="space-y-2">
                          <p className="font-semibold text-ink">{item.message}</p>
                          {item.detail ? <p className="text-xs leading-6 text-muted">{item.detail}</p> : null}
                        </div>
                      </td>
                      <td className="text-sm text-muted">
                        <div className="space-y-1">
                          <p>API: {item.api_name || "-"}</p>
                          <p>DB: {item.db_connection_name || "-"}</p>
                        </div>
                      </td>
                      <td className="font-mono text-sm text-muted">{formatStatusCode(item.status_code)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted">
                {(response.page - 1) * response.page_size + 1} -{" "}
                {Math.min(response.page * response.page_size, response.total)} / {response.total}
              </p>
              <div className="flex gap-2">
                <Link
                  className={cn("button-secondary", !hasPrevPage && "pointer-events-none opacity-50")}
                  href={hasPrevPage ? buildPageHref(resolvedSearchParams, currentPage - 1) : "#"}
                >
                  이전
                </Link>
                <Link
                  className={cn("button-secondary", !hasNextPage && "pointer-events-none opacity-50")}
                  href={hasNextPage ? buildPageHref(resolvedSearchParams, currentPage + 1) : "#"}
                >
                  다음
                </Link>
              </div>
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
