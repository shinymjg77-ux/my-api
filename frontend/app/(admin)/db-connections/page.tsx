import { DbConnectionManager } from "@/components/db-connection-manager";
import { PageHeader } from "@/components/page-header";
import { getDbConnections } from "@/lib/server-api";


function pick(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}


export default async function DbConnectionsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedSearchParams = await searchParams;
  const query = pick(resolvedSearchParams.q) ?? "";
  const isActive = pick(resolvedSearchParams.is_active) ?? "";
  const items = await getDbConnections({
    q: query || undefined,
    is_active: isActive || undefined,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="DB Connections"
        title="데이터베이스 연결 관리"
        description="운영 중인 DB 연결 정보를 보관하고, 연결 테스트 결과와 최근 상태를 함께 확인합니다."
      />

      <section className="panel p-5">
        <form className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px_auto]" method="GET">
          <label className="field">
            <span className="label">이름 검색</span>
            <input className="input" name="q" defaultValue={query} placeholder="연결 이름으로 검색" />
          </label>

          <label className="field">
            <span className="label">활성 상태</span>
            <select className="select" name="is_active" defaultValue={isActive}>
              <option value="">전체</option>
              <option value="true">활성만</option>
              <option value="false">비활성만</option>
            </select>
          </label>

          <div className="flex items-end gap-3">
            <button className="button-primary w-full md:w-auto" type="submit">
              필터 적용
            </button>
          </div>
        </form>
      </section>

      <DbConnectionManager initialItems={items} />
    </div>
  );
}
